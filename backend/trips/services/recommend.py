"""Route summaries and the recommendation order.

The document's preference order is applied lexicographically:
  1. fewest Severe miles  2. fewest High miles  3. lowest average risk  4. shortest travel time.
No Travel miles are not in the document's list; as confirmed, they are compared first because a
No Travel segment is strictly worse than a Severe one.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .risk import RiskLevel


@dataclass(frozen=True, slots=True)
class RouteSummary:
    miles_by_risk: dict[str, float]
    average_risk: float  # mile-weighted mean of Low=0 … No Travel=4
    max_risk: RiskLevel

    @property
    def no_travel(self) -> bool:
        return self.miles_by_risk[RiskLevel.NO_TRAVEL.key] > 0

    def miles(self, level: RiskLevel) -> float:
        return self.miles_by_risk[level.key]


def summarize(segments: Iterable[tuple[RiskLevel, float]]) -> RouteSummary:
    """`segments` are (risk level, miles represented) pairs, one per checkpoint."""
    miles = {level.key: 0.0 for level in RiskLevel}
    weighted = total = 0.0
    worst = RiskLevel.LOW
    for level, length in segments:
        miles[level.key] += length
        weighted += level * length
        total += length
        worst = max(worst, level)
    return RouteSummary(
        miles_by_risk={k: round(v, 1) for k, v in miles.items()},
        average_risk=round(weighted / total, 3) if total else 0.0,
        max_risk=worst,
    )


@dataclass(frozen=True, slots=True)
class Candidate:
    route_id: str
    summary: RouteSummary
    duration_s: float


# (key, label, extractor) in priority order.
CRITERIA = (
    ("no_travel_miles", "Fewest No Travel miles", lambda c: c.summary.miles(RiskLevel.NO_TRAVEL)),
    ("severe_miles", "Fewest Severe miles", lambda c: c.summary.miles(RiskLevel.SEVERE)),
    ("high_miles", "Fewest High miles", lambda c: c.summary.miles(RiskLevel.HIGH)),
    ("average_risk", "Lowest average risk", lambda c: c.summary.average_risk),
    ("travel_time", "Shortest travel time", lambda c: round(c.duration_s)),
)


def rank_key(candidate: Candidate) -> tuple:
    return tuple(extract(candidate) for _, _, extract in CRITERIA)


def _fmt(key: str, value: float) -> str:
    if key == "travel_time":
        hours, minutes = divmod(round(value / 60), 60)
        return f"{hours}h {minutes:02d}m"
    if key == "average_risk":
        return f"{value:.2f}"
    return f"{value:.1f} mi"


@dataclass(frozen=True, slots=True)
class Recommendation:
    ranking: list[str]  # route ids, best first
    route_id: str
    decided_by: str | None  # criterion key that separated #1 from #2 (None if only one route or a full tie)
    explanation: str


def recommend(candidates: list[Candidate]) -> Recommendation:
    ordered = sorted(candidates, key=rank_key)
    best = ordered[0]
    ranking = [c.route_id for c in ordered]
    if len(ordered) == 1:
        return Recommendation(ranking, best.route_id, None, "Only one route is available.")

    runner_up = ordered[1]
    for key, label, extract in CRITERIA:
        mine, theirs = extract(best), extract(runner_up)
        if mine != theirs:
            explanation = (
                f"{label}: {_fmt(key, mine)} vs {_fmt(key, theirs)} on Route {runner_up.route_id}"
                + _preceding_ties(key)
            )
            return Recommendation(ranking, best.route_id, key, explanation)
    return Recommendation(ranking, best.route_id, None, "All routes are tied on every criterion.")


def _preceding_ties(decisive_key: str) -> str:
    tied = []
    for key, label, _ in CRITERIA:
        if key == decisive_key:
            break
        tied.append(label.replace("Fewest ", "").replace("Lowest ", ""))
    return f" (tied on {', '.join(tied)})" if tied else ""
