import pytest

from trips.services.recommend import Candidate, recommend, summarize
from trips.services.risk import RiskLevel

L, M, H, S, N = RiskLevel.LOW, RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.SEVERE, RiskLevel.NO_TRAVEL


def candidate(route_id, segments, hours):
    return Candidate(route_id, summarize(segments), hours * 3600)


def test_summary_is_mile_weighted():
    summary = summarize([(L, 50), (H, 25), (S, 25)])
    assert summary.miles_by_risk == {"low": 50, "moderate": 0, "high": 25, "severe": 25, "no_travel": 0}
    assert summary.average_risk == pytest.approx((0 * 50 + 2 * 25 + 3 * 25) / 100)
    assert summary.max_risk == S
    assert summary.no_travel is False


def test_fewest_severe_miles_beats_travel_time():
    rec = recommend([candidate("A", [(L, 90), (S, 10)], 4), candidate("B", [(L, 100)], 6)])
    assert rec.route_id == "B"
    assert rec.decided_by == "severe_miles"
    assert rec.ranking == ["B", "A"]


def test_fewest_high_miles_when_severe_ties():
    rec = recommend([candidate("A", [(L, 70), (H, 30)], 4), candidate("B", [(M, 80), (H, 20)], 6)])
    assert rec.route_id == "B"
    assert rec.decided_by == "high_miles"


def test_lowest_average_risk_when_severe_and_high_tie():
    rec = recommend([candidate("A", [(M, 100)], 4), candidate("B", [(L, 50), (M, 50)], 5)])
    assert rec.route_id == "B"
    assert rec.decided_by == "average_risk"


def test_shortest_time_breaks_full_risk_tie():
    rec = recommend([candidate("A", [(L, 100)], 5), candidate("B", [(L, 100)], 4), candidate("C", [(L, 100)], 6)])
    assert rec.ranking == ["B", "A", "C"]
    assert rec.decided_by == "travel_time"
    assert "Shortest travel time: 4h 00m vs 5h 00m on Route A" in rec.explanation


def test_no_travel_miles_are_compared_first():
    """Confirmed decision: a No Travel segment is worse than any amount of Severe."""
    rec = recommend([candidate("A", [(L, 95), (N, 5)], 4), candidate("B", [(L, 50), (S, 50)], 6)])
    assert rec.route_id == "B"
    assert rec.decided_by == "no_travel_miles"


def test_explanation_lists_preceding_ties():
    rec = recommend([candidate("A", [(L, 70), (H, 30)], 4), candidate("B", [(L, 80), (H, 20)], 6)])
    assert rec.explanation == "Fewest High miles: 20.0 mi vs 30.0 mi on Route A (tied on No Travel miles, Severe miles)"


def test_single_route():
    rec = recommend([candidate("A", [(L, 10)], 1)])
    assert rec.route_id == "A" and rec.decided_by is None
