"""Checkpoints every N miles along a route, each with the truck's estimated arrival time."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .geo import LatLng
from .routing import Route


@dataclass(frozen=True, slots=True)
class Checkpoint:
    mile: float
    point: LatLng
    eta: datetime
    represents_miles: float  # route miles closest to this checkpoint (sums to the route length)


def checkpoint_miles(distance_mi: float, interval_mi: float) -> list[float]:
    """Mile 0, every `interval_mi`, and the destination."""
    count = int(distance_mi // interval_mi)
    marks = [i * interval_mi for i in range(count + 1)]
    if distance_mi - marks[-1] > 1e-6:
        marks.append(distance_mi)
    return marks


def sample_checkpoints(route: Route, interval_mi: float, departure: datetime) -> list[Checkpoint]:
    marks = checkpoint_miles(route.distance_mi, interval_mi)
    checkpoints = []
    for i, mile in enumerate(marks):
        point, seconds = route.position_at(mile)
        start = (marks[i - 1] + mile) / 2 if i > 0 else 0.0
        end = (mile + marks[i + 1]) / 2 if i < len(marks) - 1 else route.distance_mi
        checkpoints.append(
            Checkpoint(
                mile=mile,
                point=point,
                eta=departure + timedelta(seconds=seconds),
                represents_miles=end - start,
            )
        )
    return checkpoints
