"""Hourly forecasts from Open-Meteo, fetched in batches for many points at once.

Time semantics (Open-Meteo, timezone=GMT):
  * `wind_speed_10m` at stamp T is the instantaneous value at T → linearly interpolated to the ETA.
  * `rain`, `showers`, `snowfall` at stamp T are totals for the preceding hour (T−1h, T] → the hour the
    truck is driving through, [floor(ETA), floor(ETA)+1h), is the value stamped floor(ETA)+1h.
    That hourly total is the in/hr rate compared against the rain/snow thresholds.

Request budget: the free API allows 600 calls/min and every location in a request counts as a call. So:
  * points are snapped to a 0.05° lattice (≈3 mi, close to the models' native resolution) — checkpoints on
    highway shared by several routes reuse one forecast;
  * if a plan would still need more than its location budget (e.g. 10-mile checkpoints coast to coast),
    the finest coarser lattice that fits is used instead and the caller is told (see `Forecast.cell_deg`);
  * each cell's forecast window is anchored to the current UTC day (3, 6 or 10 days long) rather than to the
    departure, and cached; any cached window that covers a need is reused, so re-planning the same corridor
    with another departure, load or interval usually costs no extra calls.
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from django.conf import settings
from django.core.cache import cache

from ..exceptions import UpstreamError
from .geo import LatLng
from .http import get_http_client

LATTICES_DEG = (0.05, 0.1, 0.2, 0.3, 0.5)  # finest first
HOUR = 3600
DAY = 24 * HOUR
WINDOW_TIERS_DAYS = (3, 6, 10)  # departure ≤ 7 days + trip + 48 h heatmap; < 14 days keeps a location 1 call
CHUNK_SIZE = 50  # locations per request
MAX_PARALLEL_REQUESTS = 3  # Open-Meteo rejects too many concurrent heavy requests from one IP
BUSY_RETRIES = 3
CACHE_SECONDS = 60 * 60  # Open-Meteo refreshes its models hourly
HOURLY_VARIABLES = "wind_speed_10m,rain,showers,snowfall"

logger = logging.getLogger(__name__)

Cell = tuple[int, int, int]  # (lat index, lng index, lattice size in millidegrees)


def to_cell(point: LatLng, cell_deg: float) -> Cell:
    milli = round(cell_deg * 1000)
    return round(point[0] / cell_deg), round(point[1] / cell_deg), milli


def cell_center(cell: Cell) -> LatLng:
    lat_i, lng_i, milli = cell
    return round(lat_i * milli / 1000, 4), round(lng_i * milli / 1000, 4)


def hours_needed(ts: float) -> tuple[int, int]:
    """Hour stamps required to evaluate conditions at unix time `ts`."""
    h0 = math.floor(ts / HOUR) * HOUR
    return h0, h0 + HOUR


@dataclass(frozen=True, slots=True)
class Hourly:
    wind_mph: float | None
    rain_in: float | None  # rain + showers during the preceding hour
    snow_in: float | None  # snowfall during the preceding hour


@dataclass(frozen=True, slots=True)
class Conditions:
    wind_mph: float
    rain_in_hr: float
    snow_in_hr: float
    complete: bool  # False when the forecast had gaps (missing values are treated as 0)


class Forecast:
    def __init__(self, series: dict[Cell, dict[int, Hourly]], cell_deg: float = LATTICES_DEG[0]):
        self.series = series
        self.cell_deg = cell_deg

    def conditions(self, point: LatLng, ts: float) -> Conditions:
        hours = self.series.get(to_cell(point, self.cell_deg), {})
        h0, h1 = hours_needed(ts)
        before, after = hours.get(h0), hours.get(h1)
        w0 = before.wind_mph if before else None
        w1 = after.wind_mph if after else None
        if w0 is not None and w1 is not None:
            wind = w0 + (w1 - w0) * ((ts - h0) / HOUR)
        else:
            wind = w0 if w0 is not None else w1
        rain = after.rain_in if after else None
        snow = after.snow_in if after else None
        return Conditions(
            wind_mph=round(wind or 0.0, 1),
            rain_in_hr=round(rain or 0.0, 3),
            snow_in_hr=round(snow or 0.0, 2),
            complete=None not in (wind, rain, snow),
        )


def forecast_windows(needed_hours: Iterable[int], now: float | None = None) -> list[tuple[int, int]]:
    """Windows ([start, end] hour stamps) that cover the needs, smallest first; the first one is requested.

    Windows start at the current UTC day and come in fixed lengths, so different plans share cache entries.
    """
    now = datetime.now(UTC).timestamp() if now is None else now
    hours = list(needed_hours)
    start = math.floor(min([now - 2 * HOUR, *hours]) / DAY) * DAY
    last = max(hours)
    windows = [(start, start + days * DAY - HOUR) for days in WINDOW_TIERS_DAYS]
    return [w for w in windows if w[1] >= last] or [(start, last)]


def _hour_param(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%dT%H:%M")


def _reason(response: httpx.Response) -> str:
    try:
        return str(response.json().get("reason", ""))
    except ValueError:
        return ""


def _num(value) -> float | None:
    return None if value is None else float(value)


class WeatherClient:
    def __init__(self, http: httpx.Client | None = None, base_url: str | None = None, api_key: str | None = None):
        self.http = http or get_http_client()
        self.base_url = (base_url or settings.OPEN_METEO_BASE_URL).rstrip("/")
        self.api_key = settings.OPEN_METEO_API_KEY if api_key is None else api_key

    def forecast(
        self, points_and_times: Iterable[tuple[LatLng, float]], max_locations: int, now: float | None = None
    ) -> Forecast:
        """Forecast covering every (point, unix time) pair, using at most `max_locations` locations."""
        points_and_times = list(points_and_times)
        if not points_and_times:
            return Forecast({})
        cell_deg, needs = plan_locations(points_and_times, max_locations)
        windows = forecast_windows((h for hours in needs.values() for h in hours), now)
        start, end = windows[0]

        def key(cell: Cell, window: tuple[int, int]) -> str:
            return "wx:{}:{}:{}:{}:{}".format(*cell, *window)

        cached = cache.get_many([key(cell, w) for cell in needs for w in windows])
        series = {}
        for cell in needs:
            hit = next((cached[key(cell, w)] for w in windows if key(cell, w) in cached), None)
            if hit is not None:
                series[cell] = hit

        missing = sorted(cell for cell in needs if cell not in series)
        logger.info("weather: %d cells at %s°, %d cached, %d to fetch", len(needs), cell_deg, len(series), len(missing))
        chunks = [missing[i : i + CHUNK_SIZE] for i in range(0, len(missing), CHUNK_SIZE)]
        if chunks:
            with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_REQUESTS, len(chunks))) as pool:
                for fetched in pool.map(lambda chunk: self._fetch_chunk(chunk, start, end), chunks):
                    series.update(fetched)
                    cache.set_many({key(cell, (start, end)): hrs for cell, hrs in fetched.items()}, CACHE_SECONDS)
        return Forecast(series, cell_deg)

    def _fetch_chunk(self, chunk: list[Cell], start: int, end: int) -> dict[Cell, dict[int, Hourly]]:
        centers = [cell_center(c) for c in chunk]
        params = {
            "latitude": ",".join(f"{lat:.2f}" for lat, _ in centers),
            "longitude": ",".join(f"{lng:.2f}" for _, lng in centers),
            "hourly": HOURLY_VARIABLES,
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "GMT",
            "timeformat": "unixtime",
            "start_hour": _hour_param(start),
            "end_hour": _hour_param(end),
        }
        if self.api_key:
            params["apikey"] = self.api_key
        for attempt in range(BUSY_RETRIES + 1):
            try:
                response = self.http.get(f"{self.base_url}/v1/forecast", params=params)
            except httpx.HTTPError as exc:
                raise UpstreamError("Weather service is unreachable.") from exc
            # "Too many concurrent requests" clears in a moment; the per-minute quota does not, so only
            # the former is retried.
            if response.status_code == 429 and "concurrent" in _reason(response).lower() and attempt < BUSY_RETRIES:
                time.sleep(0.4 * (attempt + 1))
                continue
            break
        if response.status_code != 200:
            reason = _reason(response)
            logger.warning("Open-Meteo %s for %d locations: %s", response.status_code, len(chunk), reason)
            if response.status_code == 429:
                raise UpstreamError(f"Weather service rate limit reached. {reason}".strip(), status_code=503)
            raise UpstreamError(f"Weather service error ({response.status_code}). {reason}".strip())

        payload = response.json()
        locations = payload if isinstance(payload, list) else [payload]
        return {cell: self._parse_hourly(loc["hourly"]) for cell, loc in zip(chunk, locations)}

    @staticmethod
    def _parse_hourly(hourly: dict) -> dict[int, Hourly]:
        out: dict[int, Hourly] = {}
        for i, ts in enumerate(hourly["time"]):
            rain, showers = _num(hourly["rain"][i]), _num(hourly["showers"][i])
            liquid = None if rain is None and showers is None else (rain or 0.0) + (showers or 0.0)
            out[int(ts)] = Hourly(
                wind_mph=_num(hourly["wind_speed_10m"][i]),
                rain_in=liquid,
                snow_in=_num(hourly["snowfall"][i]),
            )
        return out


def needs_for(points_and_times: Iterable[tuple[LatLng, float]], cell_deg: float) -> dict[Cell, set[int]]:
    """Cell → hour stamps required to evaluate every (point, time) pair."""
    needs: dict[Cell, set[int]] = {}
    for point, ts in points_and_times:
        needs.setdefault(to_cell(point, cell_deg), set()).update(hours_needed(ts))
    return needs


def plan_locations(
    points_and_times: list[tuple[LatLng, float]], max_locations: int
) -> tuple[float, dict[Cell, set[int]]]:
    """The finest lattice whose distinct cells fit the location budget (coarsest one as a last resort)."""
    for cell_deg in LATTICES_DEG:
        needs = needs_for(points_and_times, cell_deg)
        if len(needs) <= max_locations:
            break
    return cell_deg, needs
