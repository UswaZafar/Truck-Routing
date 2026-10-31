"""Small geometry helpers. Coordinates are (lat, lng) tuples unless stated otherwise."""

from __future__ import annotations

import math
from collections.abc import Sequence

LatLng = tuple[float, float]

EARTH_RADIUS_MI = 3958.7613
METERS_PER_MILE = 1609.344
MERCATOR_RADIUS_M = 6378137.0


def haversine_mi(a: LatLng, b: LatLng) -> float:
    lat1, lng1 = map(math.radians, a)
    lat2, lng2 = map(math.radians, b)
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(min(1.0, math.sqrt(h)))


def decode_polyline(encoded: str, precision: int = 6) -> list[LatLng]:
    """Decode a Google-style encoded polyline (OSRM uses precision 6 with `geometries=polyline6`)."""
    coords: list[LatLng] = []
    index = lat = lng = 0
    factor = 10**precision
    length = len(encoded)
    while index < length:
        deltas = []
        for _ in range(2):
            result = shift = 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            deltas.append(~(result >> 1) if result & 1 else result >> 1)
        lat += deltas[0]
        lng += deltas[1]
        coords.append((lat / factor, lng / factor))
    return coords


def destination_point(origin: LatLng, bearing_deg: float, distance_mi: float) -> LatLng:
    """Point reached by travelling `distance_mi` from `origin` along an initial great-circle bearing."""
    lat1, lng1 = map(math.radians, origin)
    bearing = math.radians(bearing_deg)
    ang = distance_mi / EARTH_RADIUS_MI
    lat2 = math.asin(math.sin(lat1) * math.cos(ang) + math.cos(lat1) * math.sin(ang) * math.cos(bearing))
    lng2 = lng1 + math.atan2(
        math.sin(bearing) * math.sin(ang) * math.cos(lat1), math.cos(ang) - math.sin(lat1) * math.sin(lat2)
    )
    return math.degrees(lat2), (math.degrees(lng2) + 540) % 360 - 180


def initial_bearing_deg(a: LatLng, b: LatLng) -> float:
    lat1, lng1 = map(math.radians, a)
    lat2, lng2 = map(math.radians, b)
    y = math.sin(lng2 - lng1) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lng2 - lng1)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def lerp_point(a: LatLng, b: LatLng, t: float) -> LatLng:
    return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t


def simplify(points: Sequence[LatLng], tolerance_deg: float) -> list[LatLng]:
    """Iterative Douglas–Peucker in degree space (accurate enough for display at map scales)."""
    if len(points) < 3:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    tol_sq = tolerance_deg * tolerance_deg
    while stack:
        start, end = stack.pop()
        (ay, ax), (by, bx) = points[start], points[end]
        dx, dy = bx - ax, by - ay
        seg_len_sq = dx * dx + dy * dy
        max_dist, max_idx = -1.0, -1
        for i in range(start + 1, end):
            py, px = points[i]
            if seg_len_sq == 0:
                dist = (px - ax) ** 2 + (py - ay) ** 2
            else:
                t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_len_sq))
                dist = (px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2
            if dist > max_dist:
                max_dist, max_idx = dist, i
        if max_dist > tol_sq:
            keep[max_idx] = True
            stack.append((start, max_idx))
            stack.append((max_idx, end))
    return [p for p, k in zip(points, keep) if k]


def to_mercator(point: LatLng) -> tuple[float, float]:
    """(lat, lng) → Web-Mercator (x, y) metres."""
    lat = max(min(point[0], 85.05112878), -85.05112878)
    x = MERCATOR_RADIUS_M * math.radians(point[1])
    y = MERCATOR_RADIUS_M * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    return x, y


def from_mercator(x: float, y: float) -> LatLng:
    lng = math.degrees(x / MERCATOR_RADIUS_M)
    lat = math.degrees(2 * math.atan(math.exp(y / MERCATOR_RADIUS_M)) - math.pi / 2)
    return lat, lng
