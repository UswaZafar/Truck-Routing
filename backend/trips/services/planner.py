"""Trip planning pipeline: routes → checkpoints at ETAs → weather → risk → summaries → recommendation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from django.conf import settings
from rest_framework.exceptions import ValidationError

from ..exceptions import NoRouteError
from .checkpoints import sample_checkpoints
from .geo import haversine_mi, simplify
from .geocoding import GeocodingClient
from .recommend import Candidate, recommend, summarize
from .risk import assess
from .routing import ROUTE_COUNT, Route, RoutingClient
from .weather import LATTICES_DEG, WeatherClient

ROUTE_IDS = "ABC"
GEOMETRY_TOLERANCE_DEG = 0.0005  # ≈50 m; keeps map geometry light without visible change
MIN_TRIP_MILES = 0.5


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def resolve_place(value: str | dict, field: str, geocoder: GeocodingClient) -> dict:
    """Places arrive as {label, lat, lng} (picked from suggestions) or free text to geocode."""
    if isinstance(value, dict):
        return value
    place = geocoder.resolve(value)
    if place is None:
        raise ValidationError({field: [f'No place found for "{value}".']})
    return place


def resolve_places(origin, destination, geocoder: GeocodingClient | None = None) -> tuple[dict, dict]:
    geocoder = geocoder or GeocodingClient()
    origin = resolve_place(origin, "origin", geocoder)
    destination = resolve_place(destination, "destination", geocoder)
    if haversine_mi((origin["lat"], origin["lng"]), (destination["lat"], destination["lng"])) < MIN_TRIP_MILES:
        raise ValidationError({"destination": ["Destination must be different from the origin."]})
    return origin, destination


def compute_plan(
    origin: dict,
    destination: dict,
    departure_at: datetime,
    load_weight_lb: int,
    interval_miles: int,
    routing: RoutingClient | None = None,
    weather: WeatherClient | None = None,
) -> dict:
    routing = routing or RoutingClient()
    weather = weather or WeatherClient()

    routes = routing.find_routes((origin["lat"], origin["lng"]), (destination["lat"], destination["lng"]))
    if not routes:
        raise NoRouteError()
    sampled = [sample_checkpoints(route, interval_miles, departure_at) for route in routes]
    forecast = weather.forecast(
        ((cp.point, cp.eta.timestamp()) for cps in sampled for cp in cps),
        max_locations=settings.WEATHER_CHECKPOINT_LOCATIONS,
    )

    payloads, candidates = [], []
    incomplete = False
    for route_id, route, checkpoints in zip(ROUTE_IDS, routes, sampled):
        segments, checkpoint_payloads = [], []
        for cp in checkpoints:
            cond = forecast.conditions(cp.point, cp.eta.timestamp())
            result = assess(cond.wind_mph, cond.rain_in_hr, cond.snow_in_hr, load_weight_lb)
            segments.append((result.level, cp.represents_miles))
            incomplete |= not cond.complete
            checkpoint_payloads.append(
                {
                    "mile": round(cp.mile, 1),
                    "lat": round(cp.point[0], 5),
                    "lng": round(cp.point[1], 5),
                    "eta": iso(cp.eta),
                    "wind_mph": cond.wind_mph,
                    "rain_in_hr": cond.rain_in_hr,
                    "snow_in_hr": cond.snow_in_hr,
                    "risk": result.level.key,
                    "conditions": list(result.conditions),
                    "load_adjusted": result.load_adjusted,
                    "miles": round(cp.represents_miles, 2),
                    "forecast_complete": cond.complete,
                }
            )
        summary = summarize(segments)
        candidates.append(Candidate(route_id, summary, route.duration_s))
        payloads.append(_route_payload(route_id, route, departure_at, summary, checkpoint_payloads))

    rec = recommend(candidates)
    for payload in payloads:
        payload["rank"] = rec.ranking.index(payload["id"]) + 1
        payload["recommended"] = payload["id"] == rec.route_id

    notes = []
    if len(routes) < ROUTE_COUNT:
        notes.append(f"Only {len(routes)} distinct route(s) exist between these places.")
    if forecast.cell_deg > LATTICES_DEG[0]:
        notes.append(
            f"To stay within the free weather API limit, checkpoint forecasts use a {forecast.cell_deg}° grid "
            f"(≈{forecast.cell_deg * 69:.0f} mi) instead of the default {LATTICES_DEG[0]}°."
        )
    if incomplete:
        notes.append("Some checkpoints are beyond the forecast horizon; missing values were treated as zero.")
    return {
        "recommendation": {
            "route_id": rec.route_id,
            "ranking": rec.ranking,
            "decided_by": rec.decided_by,
            "explanation": rec.explanation,
        },
        "routes": payloads,
        "notes": notes,
    }


def _route_payload(route_id: str, route: Route, departure_at: datetime, summary, checkpoints: list[dict]) -> dict:
    geometry = simplify(route.points, GEOMETRY_TOLERANCE_DEG)
    return {
        "id": route_id,
        "source": route.source,
        "distance_mi": round(route.distance_mi, 1),
        "duration_s": round(route.duration_s),
        "arrival_at": iso(departure_at + timedelta(seconds=route.duration_s)),
        "geometry": [[round(lng, 5), round(lat, 5)] for lat, lng in geometry],
        "summary": {
            "miles_by_risk": summary.miles_by_risk,
            "average_risk": summary.average_risk,
            "max_risk": summary.max_risk.key,
            "no_travel": summary.no_travel,
        },
        "checkpoints": checkpoints,
    }
