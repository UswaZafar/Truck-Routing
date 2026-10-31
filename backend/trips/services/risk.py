"""Weather risk classification — a direct encoding of the assessment's risk and load rules.

Threshold table (bands are lower-bound inclusive where the document's ranges share an edge):

    Condition  Low        Moderate     High         Severe       No Travel
    Wind       <25 mph    25–34        35–44        45–54        ≥55 mph
    Rain       <0.10 in/hr 0.10–0.25   0.25–0.50    0.50–1.00    >1.00
    Snow       <0.5 in/hr 0.5–1.0      1.0–2.0      2.0–3.0      >3.0

Load rules:
    ≥55 mph                     → No Travel for any load
    45–54 mph and >30,000 lb    → No Travel
    35–44 mph and >40,000 lb    → Severe
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class RiskLevel(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def key(self) -> str:
        return self.name.lower()


# Lower edges of Moderate, High and Severe; the last tuple item is the No Travel edge.
WIND_EDGES_MPH = (25.0, 35.0, 45.0, 55.0)  # No Travel is "≥55" → inclusive
RAIN_EDGES_IN_HR = (0.10, 0.25, 0.50, 1.00)  # No Travel is ">1.00" → exclusive
SNOW_EDGES_IN_HR = (0.5, 1.0, 2.0, 3.0)  # No Travel is ">3.0" → exclusive

HEAVY_LOAD_NO_TRAVEL_LB = 30_000  # 45–54 mph + >30,000 lb → No Travel
HEAVY_LOAD_SEVERE_LB = 40_000  # 35–44 mph + >40,000 lb → Severe


def _band(value: float, edges: tuple[float, float, float, float], no_travel_inclusive: bool) -> RiskLevel:
    moderate, high, severe, no_travel = edges
    if value > no_travel or (no_travel_inclusive and value == no_travel):
        return RiskLevel.NO_TRAVEL
    if value >= severe:
        return RiskLevel.SEVERE
    if value >= high:
        return RiskLevel.HIGH
    if value >= moderate:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def wind_level(wind_mph: float, load_weight_lb: float) -> RiskLevel:
    """Wind band from the threshold table, escalated by the load rules."""
    level = _band(wind_mph, WIND_EDGES_MPH, no_travel_inclusive=True)
    if level == RiskLevel.SEVERE and load_weight_lb > HEAVY_LOAD_NO_TRAVEL_LB:
        return RiskLevel.NO_TRAVEL
    if level == RiskLevel.HIGH and load_weight_lb > HEAVY_LOAD_SEVERE_LB:
        return RiskLevel.SEVERE
    return level


def rain_level(rain_in_hr: float) -> RiskLevel:
    return _band(rain_in_hr, RAIN_EDGES_IN_HR, no_travel_inclusive=False)


def snow_level(snow_in_hr: float) -> RiskLevel:
    return _band(snow_in_hr, SNOW_EDGES_IN_HR, no_travel_inclusive=False)


@dataclass(frozen=True, slots=True)
class Assessment:
    level: RiskLevel
    conditions: tuple[str, ...]  # which of "wind", "rain", "snow" produced the level (empty when Low)
    load_adjusted: bool  # True when a load rule raised the wind level


def assess(wind_mph: float, rain_in_hr: float, snow_in_hr: float, load_weight_lb: float) -> Assessment:
    """Checkpoint risk = the worst of wind (after load rules), rain and snow."""
    base_wind = _band(wind_mph, WIND_EDGES_MPH, no_travel_inclusive=True)
    levels = {
        "wind": wind_level(wind_mph, load_weight_lb),
        "rain": rain_level(rain_in_hr),
        "snow": snow_level(snow_in_hr),
    }
    worst = max(levels.values())
    conditions = tuple(name for name, lvl in levels.items() if lvl == worst) if worst > RiskLevel.LOW else ()
    return Assessment(
        level=worst,
        conditions=conditions,
        load_adjusted="wind" in conditions and levels["wind"] > base_wind,
    )


def _band_fraction(value: float, edges: tuple[float, ...], level: RiskLevel) -> float:
    """Position of `value` inside its band, in [0, 1)."""
    if level == RiskLevel.NO_TRAVEL:
        return 0.0
    lower = 0.0 if level == RiskLevel.LOW else edges[level - 1]
    upper = edges[level]
    return min(max((value - lower) / (upper - lower), 0.0), 0.99)


def risk_index(wind_mph: float, rain_in_hr: float, snow_in_hr: float, load_weight_lb: float) -> float:
    """Continuous 0–4 index for the heatmap whose integer part always equals the discrete risk level.

    Each condition contributes `level + position within its band`; the worst contribution wins. A load rule
    that escalates the wind level snaps the wind contribution to the start of the escalated band.
    """
    contributions = []
    for value, edges, level in (
        (wind_mph, WIND_EDGES_MPH, _band(wind_mph, WIND_EDGES_MPH, no_travel_inclusive=True)),
        (rain_in_hr, RAIN_EDGES_IN_HR, rain_level(rain_in_hr)),
        (snow_in_hr, SNOW_EDGES_IN_HR, snow_level(snow_in_hr)),
    ):
        contributions.append(level + _band_fraction(value, edges, level))
    contributions.append(float(wind_level(wind_mph, load_weight_lb)))
    return round(max(contributions), 2)
