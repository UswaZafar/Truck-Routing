"""Weather risk heatmap for the trip corridor, hour by hour from departure (0–48 h).

The corridor is a regular grid in Web-Mercator metres (square on screen at every latitude), limited to cells
within CORRIDOR_HALF_WIDTH_MI of any route. The frontend draws the grid as a tiny image stretched over
`bounds`; one pixel per cell, so a cell index is simply `row * cols + col` with row 0 at the north edge.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime

from .geo import METERS_PER_MILE, LatLng, from_mercator, haversine_mi, to_mercator
from .risk import risk_index
from .weather import HOUR, WeatherClient

HEATMAP_HOURS = 49  # slider positions 0…48
CORRIDOR_HALF_WIDTH_MI = 40.0
BASE_CELL_MI = 12.0
CELL_GROWTH = 1.2


@dataclass(frozen=True, slots=True)
class Grid:
    cell_m: float  # Mercator metres
    min_col: int
    max_col: int
    min_row: int
    max_row: int
    cells: tuple[tuple[int, int], ...]  # (col, row) in global Mercator lattice, sorted

    @property
    def cols(self) -> int:
        return self.max_col - self.min_col + 1

    @property
    def rows(self) -> int:
        return self.max_row - self.min_row + 1

    def center(self, col: int, row: int) -> LatLng:
        return from_mercator((col + 0.5) * self.cell_m, (row + 0.5) * self.cell_m)

    def image_index(self, col: int, row: int) -> int:
        return (self.max_row - row) * self.cols + (col - self.min_col)

    def bounds(self) -> list[list[float]]:
        """Image corners as [lng, lat]: top-left, top-right, bottom-right, bottom-left."""
        north, west = from_mercator(self.min_col * self.cell_m, (self.max_row + 1) * self.cell_m)
        south, east = from_mercator((self.max_col + 1) * self.cell_m, self.min_row * self.cell_m)
        return [
            [round(west, 5), round(north, 5)],
            [round(east, 5), round(north, 5)],
            [round(east, 5), round(south, 5)],
            [round(west, 5), round(south, 5)],
        ]


def _resample(line: list[LatLng], step_mi: float) -> list[LatLng]:
    """Points at most `step_mi` apart along a polyline."""
    out = [line[0]]
    for a, b in zip(line, line[1:]):
        n = max(1, math.ceil(haversine_mi(a, b) / step_mi))
        out.extend((a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(1, n + 1))
    return out


def _corridor_cells(lines: list[list[LatLng]], cell_mi_at_equator: float) -> tuple[float, set[tuple[int, int]]]:
    cell_m = cell_mi_at_equator * METERS_PER_MILE
    cells: set[tuple[int, int]] = set()
    for line in lines:
        for point in _resample(line, cell_mi_at_equator / 2):
            x, y = to_mercator(point)
            stretch = 1 / math.cos(math.radians(point[0]))  # Mercator metres per ground metre here
            radius = CORRIDOR_HALF_WIDTH_MI * METERS_PER_MILE * stretch
            for col in range(math.floor((x - radius) / cell_m), math.floor((x + radius) / cell_m) + 1):
                for row in range(math.floor((y - radius) / cell_m), math.floor((y + radius) / cell_m) + 1):
                    cx, cy = (col + 0.5) * cell_m, (row + 0.5) * cell_m
                    if (cx - x) ** 2 + (cy - y) ** 2 <= radius * radius:
                        cells.add((col, row))
    return cell_m, cells


def build_grid(lines: list[list[LatLng]], max_cells: int) -> Grid:
    """Corridor grid around all routes, coarsened until it has at most `max_cells` cells (1 API call each)."""
    mid_lat = sum(p[0] for line in lines for p in line) / sum(len(line) for line in lines)
    # Express the target ground size as Mercator size at the corridor's mean latitude.
    cell_mi = BASE_CELL_MI / math.cos(math.radians(mid_lat))
    while True:
        cell_m, cells = _corridor_cells(lines, cell_mi)
        if len(cells) <= max_cells:
            break
        cell_mi *= CELL_GROWTH
    cols = [c for c, _ in cells]
    rows = [r for _, r in cells]
    return Grid(cell_m, min(cols), max(cols), min(rows), max(rows), tuple(sorted(cells)))


def floor_hour(dt: datetime) -> int:
    return math.floor(dt.timestamp() / HOUR) * HOUR


def build_heatmap(
    lines: list[list[LatLng]], departure: datetime, load_weight_lb: int, client: WeatherClient, max_cells: int
) -> dict:
    """Heatmap payload: per hour slot, the risk index ×10 (int 0–40, None if unavailable) for every cell.

    Slot 0 is the departure hour. Slot h uses wind at that hour and precipitation for the following hour,
    the same rule as checkpoints (see weather.py).
    """
    grid = build_grid(lines, max_cells)
    start = floor_hour(departure)
    slots = [start + h * HOUR for h in range(HEATMAP_HOURS)]
    centers = [grid.center(col, row) for col, row in grid.cells]
    # Each cell is fetched over one contiguous window, so the first and last slot bound all 49 hours.
    forecast = client.forecast(((c, ts) for c in centers for ts in (slots[0], slots[-1])), max_cells)

    values = []
    for ts in slots:
        row_values = []
        for center in centers:
            cond = forecast.conditions(center, ts)
            if cond.complete:
                index = risk_index(cond.wind_mph, cond.rain_in_hr, cond.snow_in_hr, load_weight_lb)
                row_values.append(round(index * 10))
            else:
                row_values.append(None)
        values.append(row_values)

    return {
        "start": datetime.fromtimestamp(start, tz=UTC).isoformat().replace("+00:00", "Z"),
        "hours": HEATMAP_HOURS,
        "grid": {"cols": grid.cols, "rows": grid.rows, "bounds": grid.bounds()},
        "cells": [grid.image_index(col, row) for col, row in grid.cells],
        "values": values,
    }
