"""In-process fakes for OSRM, Photon and Open-Meteo, served through httpx.MockTransport."""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import unquote

import httpx

from trips.services.geo import LatLng, haversine_mi
from trips.services.routing import Route


def encode_polyline(points: list[LatLng], precision: int = 6) -> str:
    factor = 10**precision
    out, prev_lat, prev_lng = [], 0, 0
    for lat, lng in points:
        ilat, ilng = round(lat * factor), round(lng * factor)
        for delta in (ilat - prev_lat, ilng - prev_lng):
            value = ~(delta << 1) if delta < 0 else delta << 1
            while value >= 0x20:
                out.append(chr((0x20 | (value & 0x1F)) + 63))
                value >>= 5
            out.append(chr(value + 63))
        prev_lat, prev_lng = ilat, ilng
    return "".join(out)


def straight_points(a: LatLng, b: LatLng, n: int) -> list[LatLng]:
    return [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n + 1)]


def make_route(points: list[LatLng], mph: float = 60.0, source: str = "osrm") -> Route:
    cum_miles, cum_seconds = [0.0], [0.0]
    for a, b in zip(points, points[1:]):
        d = haversine_mi(a, b)
        cum_miles.append(cum_miles[-1] + d)
        cum_seconds.append(cum_seconds[-1] + d / mph * 3600)
    return Route(points=points, cum_miles=cum_miles, cum_seconds=cum_seconds, source=source)


def osrm_route_json(waypoints: list[LatLng], mph: float = 60.0, per_leg: int = 40) -> dict:
    """An OSRM route object through the waypoints (straight legs at constant speed)."""
    points: list[LatLng] = [waypoints[0]]
    legs = []
    for a, b in zip(waypoints, waypoints[1:]):
        leg_points = straight_points(a, b, per_leg)
        durations = [haversine_mi(p, q) / mph * 3600 for p, q in zip(leg_points, leg_points[1:])]
        points.extend(leg_points[1:])
        legs.append({"duration": sum(durations), "annotation": {"duration": durations}})
    total = sum(leg["duration"] for leg in legs)
    return {"geometry": encode_polyline(points), "legs": legs, "duration": total, "distance": 0}


def parse_coords(path: str) -> list[LatLng]:
    coords = unquote(path.rsplit("/", 1)[-1])
    return [(float(lat), float(lng)) for lng, lat in (pair.split(",") for pair in coords.split(";"))]


WeatherFn = Callable[[float, float, int], tuple[float, float, float, float]]


def calm(_lat: float, _lng: float, _ts: int) -> tuple[float, float, float, float]:
    """(wind mph, rain in, showers in, snowfall in)."""
    return 5.0, 0.0, 0.0, 0.0


def open_meteo_json(request: httpx.Request, weather: WeatherFn) -> list[dict]:
    params = request.url.params
    lats = [float(v) for v in params["latitude"].split(",")]
    lngs = [float(v) for v in params["longitude"].split(",")]
    start = int(datetime.strptime(params["start_hour"], "%Y-%m-%dT%H:%M").replace(tzinfo=UTC).timestamp())
    end = int(datetime.strptime(params["end_hour"], "%Y-%m-%dT%H:%M").replace(tzinfo=UTC).timestamp())
    times = list(range(start, end + 1, 3600))
    out = []
    for lat, lng in zip(lats, lngs):
        values = [weather(lat, lng, ts) for ts in times]
        out.append(
            {
                "latitude": lat,
                "longitude": lng,
                "hourly": {
                    "time": times,
                    "wind_speed_10m": [v[0] for v in values],
                    "rain": [v[1] for v in values],
                    "showers": [v[2] for v in values],
                    "snowfall": [v[3] for v in values],
                },
            }
        )
    return out


class FakeProviders:
    """Routes every provider URL to a fake; counts calls per provider."""

    def __init__(self, weather: WeatherFn = calm, osrm_routes: int = 1, osrm_status: int = 200):
        self.weather = weather
        self.osrm_routes = osrm_routes
        self.osrm_status = osrm_status
        self.calls: dict[str, int] = {"osrm": 0, "photon": 0, "open-meteo": 0}
        self.weather_locations = 0
        self.weather_status = 200

    def handler(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if "osrm" in host:
            self.calls["osrm"] += 1
            if self.osrm_status != 200:
                return httpx.Response(self.osrm_status, json={"code": "Error"})
            waypoints = parse_coords(request.url.path)
            if request.url.params.get("alternatives") not in (None, "false"):
                routes = [osrm_route_json(waypoints)]
                # Extra OSRM alternatives bend through a point east of the midpoint.
                for k in range(1, self.osrm_routes):
                    mid = ((waypoints[0][0] + waypoints[-1][0]) / 2, (waypoints[0][1] + waypoints[-1][1]) / 2)
                    routes.append(osrm_route_json([waypoints[0], (mid[0], mid[1] + 0.6 * k), waypoints[-1]]))
                return httpx.Response(200, json={"code": "Ok", "routes": routes})
            return httpx.Response(200, json={"code": "Ok", "routes": [osrm_route_json(waypoints)]})
        if "photon" in host:
            self.calls["photon"] += 1
            q = request.url.params["q"].lower()
            if "nowhere" in q:
                return httpx.Response(200, json={"features": []})
            lat, lng = (32.7767, -96.797) if "dallas" in q else (29.7604, -95.3698)
            name = "Dallas" if "dallas" in q else "Houston"
            return httpx.Response(
                200,
                json={
                    "features": [
                        {
                            "geometry": {"coordinates": [lng, lat]},
                            "properties": {"name": name, "state": "Texas", "country": "United States"},
                        }
                    ]
                },
            )
        if "open-meteo" in host:
            self.calls["open-meteo"] += 1
            if self.weather_status != 200:
                return httpx.Response(self.weather_status, json={"error": True, "reason": "Too many requests"})
            payload = open_meteo_json(request, self.weather)
            self.weather_locations += len(payload)
            return httpx.Response(200, json=payload if len(payload) > 1 else payload[0])
        return httpx.Response(404)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handler))


def hours_from(dt: datetime) -> int:
    return math.floor(dt.timestamp() / 3600) * 3600
