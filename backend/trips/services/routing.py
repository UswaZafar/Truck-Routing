"""Route options from OSRM, topped up to three distinct alternatives with via-point detours.

The public OSRM server often returns only one or two routes even with `alternatives=3`. So, alongside the
main request, we route through points offset perpendicular to the trip and keep candidates that are genuinely
different (not mostly overlapping a kept route), are not out-and-back spurs and are not much slower. Further
probe pairs are only sent if needed: the public server queues bursts, so fewer requests means faster plans.
Corridors with a single real highway may have no detour that passes the strict filters; a final relaxed pass
then still provides three options (the recommendation ranks them anyway).
"""

from __future__ import annotations

import logging
from bisect import bisect_right
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field

import httpx
from django.conf import settings
from django.core.cache import cache

from ..exceptions import NoRouteError, UpstreamError
from .geo import (
    LatLng,
    decode_polyline,
    destination_point,
    haversine_mi,
    initial_bearing_deg,
    lerp_point,
)
from .http import get_http_client

logger = logging.getLogger(__name__)

ROUTE_COUNT = 3


@dataclass(frozen=True, slots=True)
class DetourLimits:
    max_duration_ratio: float  # vs the fastest route
    max_overlap: float  # share of length shared with any kept route
    max_backtrack: float  # share of length driven out and back along the same road


STRICT = DetourLimits(max_duration_ratio=1.6, max_overlap=0.85, max_backtrack=0.05)
RELAXED = DetourLimits(max_duration_ratio=2.0, max_overlap=0.9, max_backtrack=0.1)
ROUTE_CACHE_SECONDS = 60 * 60
PRIMARY_TIMEOUT_SECONDS = 15.0
PRIMARY_RETRIES = 1
VIA_TIMEOUT_SECONDS = 6.0  # detour candidates are optional: use those that answer in time, skip the rest

# Probe batches: (fraction of the straight origin→destination line, offset as a share of its length),
# each probed on both sides. The first batch is sent together with the main request.
VIA_BATCHES = (
    [(0.5, 0.2)],
    [(0.33, 0.2), (0.67, 0.2)],
    [(0.5, 0.4)],
)
MIN_OFFSET_MI, MAX_OFFSET_MI = 3.0, 150.0


@dataclass(slots=True)
class Route:
    """A drivable route with cumulative distance (miles) and time (seconds) at every vertex."""

    points: list[LatLng]
    cum_miles: list[float]
    cum_seconds: list[float]
    source: str = "osrm"
    _samples: list[LatLng] | None = field(default=None, repr=False)
    _cells: frozenset | None = field(default=None, repr=False)

    @property
    def distance_mi(self) -> float:
        return self.cum_miles[-1]

    @property
    def duration_s(self) -> float:
        return self.cum_seconds[-1]

    def position_at(self, mile: float) -> tuple[LatLng, float]:
        """Interpolated (point, seconds-from-departure) at a given mile along the route."""
        mile = min(max(mile, 0.0), self.distance_mi)
        i = min(bisect_right(self.cum_miles, mile) - 1, len(self.points) - 2)
        span = self.cum_miles[i + 1] - self.cum_miles[i]
        t = (mile - self.cum_miles[i]) / span if span > 0 else 0.0
        seconds = self.cum_seconds[i] + (self.cum_seconds[i + 1] - self.cum_seconds[i]) * t
        return lerp_point(self.points[i], self.points[i + 1], t), seconds

    def samples(self) -> list[LatLng]:
        """Points every mile along the route (memoised; used for overlap checks)."""
        if self._samples is None:
            count = max(int(self.distance_mi), 1)
            self._samples = [self.position_at(i)[0] for i in range(count + 1)]
        return self._samples

    def cells(self) -> frozenset:
        """Coarse occupancy grid (~0.7 mi cells) used for overlap checks."""
        if self._cells is None:
            self._cells = frozenset(_cell(p) for p in self.samples())
        return self._cells


def _cell(p: LatLng) -> tuple[int, int]:
    return round(p[0] / 0.01), round(p[1] / 0.01)


def _near(cell: tuple[int, int], cells) -> bool:
    r, c = cell
    return any((r + dr, c + dc) in cells for dr in (-1, 0, 1) for dc in (-1, 0, 1))


def overlap_ratio(candidate: Route, other: Route) -> float:
    """Share of the candidate's length that runs along `other`."""
    samples = candidate.samples()
    other_cells = other.cells()
    return sum(_near(_cell(p), other_cells) for p in samples) / len(samples)


def backtrack_ratio(route: Route) -> float:
    """Share of samples that revisit a spot passed more than 5 miles earlier (out-and-back spurs)."""
    first_seen: dict[tuple[int, int], int] = {}
    revisits = 0
    samples = route.samples()
    for i, p in enumerate(samples):
        cell = _cell(p)
        r, c = cell
        earlier = [
            first_seen[k]
            for k in ((r + dr, c + dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1))
            if k in first_seen
        ]
        if earlier and i - min(earlier) > 5:
            revisits += 1
        first_seen.setdefault(cell, i)
    return revisits / len(samples)


def parse_osrm_route(data: dict, source: str) -> Route:
    """Build a Route from an OSRM route object (overview=full, polyline6, duration annotations).

    Segment lengths come from the geometry (OSRM's own distances are haversine too, and leaving them out
    halves the response). Annotated durations exclude turn penalties, so each leg's durations are scaled
    to sum to the leg's total — the time is spread over the leg in proportion to the driving time.
    """
    points = decode_polyline(data["geometry"], precision=6)
    seg_miles = [haversine_mi(a, b) for a, b in zip(points, points[1:])]
    seg_seconds: list[float] = []
    for leg in data["legs"]:
        durations = (leg.get("annotation") or {}).get("duration") or []
        total = sum(durations)
        scale = leg["duration"] / total if total > 0 else 1.0
        seg_seconds.extend(d * scale for d in durations)

    if len(seg_seconds) != len(seg_miles):
        # Defensive fallback: spread the total duration by distance.
        total_mi = sum(seg_miles) or 1.0
        seg_seconds = [m / total_mi * data["duration"] for m in seg_miles]

    cum_miles, cum_seconds = [0.0], [0.0]
    for m, s in zip(seg_miles, seg_seconds):
        cum_miles.append(cum_miles[-1] + m)
        cum_seconds.append(cum_seconds[-1] + s)
    return Route(points=points, cum_miles=cum_miles, cum_seconds=cum_seconds, source=source)


class RoutingClient:
    def __init__(self, http: httpx.Client | None = None, base_url: str | None = None):
        self.http = http or get_http_client()
        self.base_url = (base_url or settings.OSRM_BASE_URL).rstrip("/")

    def route(
        self,
        waypoints: list[LatLng],
        alternatives: int = 0,
        source: str = "osrm",
        timeout: float | None = None,
        retries: int = 0,
    ) -> list[Route]:
        """Routes through `waypoints` with full geometry and per-segment durations."""
        coords = ";".join(f"{lng:.6f},{lat:.6f}" for lat, lng in waypoints)
        params = {
            "overview": "full",
            "geometries": "polyline6",
            "annotations": "duration",
            "steps": "false",
            "alternatives": str(alternatives) if alternatives else "false",
        }
        url = f"{self.base_url}/route/v1/driving/{coords}"
        for attempt in range(retries + 1):
            try:
                response = self.http.get(url, params=params, timeout=timeout or httpx.USE_CLIENT_DEFAULT)
                break
            except httpx.HTTPError as exc:
                if attempt == retries:
                    raise UpstreamError("Routing service is unreachable.") from exc
                logger.warning("OSRM request failed (%s), retrying", exc)
        payload = _json_or_none(response)
        code = (payload or {}).get("code")
        if code in {"NoRoute", "NoSegment"}:
            raise NoRouteError("No drivable route was found between these places.")
        if response.status_code == 429:
            raise UpstreamError("Routing service rate limit reached. Please retry shortly.", status_code=503)
        if response.status_code != 200 or code != "Ok":
            raise UpstreamError(f"Routing service error ({response.status_code}).")
        return [parse_osrm_route(r, source) for r in payload["routes"]]

    def find_routes(self, origin: LatLng, destination: LatLng, count: int = ROUTE_COUNT) -> list[Route]:
        """Up to `count` distinct routes, fastest first."""
        key = f"routes:{origin[0]:.5f},{origin[1]:.5f}:{destination[0]:.5f},{destination[1]:.5f}:{count}"
        cached = cache.get(key)
        if cached is not None:
            return cached

        # Not a `with` block: slow detour probes must not hold up the response once we have enough routes.
        pool = ThreadPoolExecutor(max_workers=5)
        try:
            main = pool.submit(
                self.route,
                [origin, destination],
                alternatives=count,
                timeout=PRIMARY_TIMEOUT_SECONDS,
                retries=PRIMARY_RETRIES,
            )
            probes = self._probe(pool, origin, destination, VIA_BATCHES[0])
            kept = sorted(main.result(), key=lambda r: r.duration_s)[:count]
            answered: list[Route] = []
            for batch_index, batch in enumerate(VIA_BATCHES):
                if not kept or len(kept) >= count:  # nothing to detour from, or already enough
                    break
                if batch_index > 0:
                    probes += self._probe(pool, origin, destination, batch)
                wait(probes[-2 * len(batch) :], timeout=VIA_TIMEOUT_SECONDS)
                # Includes late answers to earlier batches.
                answered = [f.result() for f in probes if f.done() and f.result() is not None]
                kept += pick_detours(kept, answered, count - len(kept), STRICT)
            if kept and len(kept) < count:
                kept += pick_detours(kept, answered, count - len(kept), RELAXED)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

        kept.sort(key=lambda r: r.duration_s)
        cache.set(key, kept, ROUTE_CACHE_SECONDS)
        return kept

    def _probe(self, pool, origin, destination, batch) -> list[Future]:
        straight_mi = haversine_mi(origin, destination)
        bearing = initial_bearing_deg(origin, destination)
        probes = []
        for fraction, share in batch:
            anchor = destination_point(origin, bearing, straight_mi * fraction)
            offset = min(max(straight_mi * share, MIN_OFFSET_MI), MAX_OFFSET_MI)
            for side in (90, -90):
                via = destination_point(anchor, bearing + side, offset)
                probes.append(pool.submit(self._try_via, origin, via, destination))
        return probes

    def _try_via(self, origin, via, destination) -> Route | None:
        try:
            return self.route([origin, via, destination], source="osrm-via", timeout=VIA_TIMEOUT_SECONDS)[0]
        except (NoRouteError, UpstreamError) as exc:
            logger.info("via candidate %s skipped: %s", via, exc)
            return None


def pick_detours(kept: list[Route], candidates: list[Route], wanted: int, limits: DetourLimits) -> list[Route]:
    """Up to `wanted` candidates within `limits`, fastest first, each distinct from all routes kept so far."""
    fastest = kept[0]
    chosen: list[Route] = []
    for candidate in sorted(candidates, key=lambda r: r.duration_s):
        if len(chosen) >= wanted:
            break
        if candidate.duration_s > fastest.duration_s * limits.max_duration_ratio:
            continue
        if backtrack_ratio(candidate) > limits.max_backtrack:
            continue
        if all(overlap_ratio(candidate, other) <= limits.max_overlap for other in [*kept, *chosen]):
            chosen.append(candidate)
    return chosen


def _json_or_none(response: httpx.Response) -> dict | None:
    try:
        return response.json()
    except ValueError:
        return None
