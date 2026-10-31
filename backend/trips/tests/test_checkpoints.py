from datetime import UTC, datetime, timedelta

import pytest

from trips.services.checkpoints import checkpoint_miles, sample_checkpoints
from trips.services.geo import haversine_mi

from .fakes import make_route, straight_points

DEPARTURE = datetime(2026, 11, 2, 8, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "distance, interval, expected",
    [
        (100, 25, [0, 25, 50, 75, 100]),
        (101, 25, [0, 25, 50, 75, 100, 101]),
        (30, 50, [0, 30]),
        (12, 10, [0, 10, 12]),
    ],
)
def test_checkpoint_miles(distance, interval, expected):
    assert checkpoint_miles(distance, interval) == pytest.approx(expected)


@pytest.mark.parametrize("interval", [10, 25, 50])
def test_checkpoints_follow_the_interval_and_eta(interval):
    route = make_route(straight_points((30.0, -97.0), (32.5, -97.0), 50), mph=50)
    checkpoints = sample_checkpoints(route, interval, DEPARTURE)

    assert checkpoints[0].mile == 0 and checkpoints[0].eta == DEPARTURE
    assert checkpoints[-1].mile == pytest.approx(route.distance_mi)
    assert checkpoints[-1].eta == DEPARTURE + timedelta(seconds=route.duration_s)
    for a, b in zip(checkpoints, checkpoints[1:]):
        assert b.eta > a.eta
    for cp in checkpoints[1:-1]:
        assert cp.mile % interval == pytest.approx(0)
        # Constant 50 mph → ETA is exactly mile / 50 hours after departure.
        assert (cp.eta - DEPARTURE).total_seconds() == pytest.approx(cp.mile / 50 * 3600, abs=1)
        # The point really is `mile` miles from the start along the (straight) route.
        assert haversine_mi(route.points[0], cp.point) == pytest.approx(cp.mile, rel=1e-3)


def test_represented_miles_sum_to_route_length():
    route = make_route(straight_points((30.0, -97.0), (31.3, -96.0), 40))
    checkpoints = sample_checkpoints(route, 25, DEPARTURE)
    assert sum(cp.represents_miles for cp in checkpoints) == pytest.approx(route.distance_mi)
    assert checkpoints[0].represents_miles == pytest.approx(12.5)


def test_eta_follows_variable_speed():
    """Slow first half (30 mph), fast second half (60 mph): checkpoints reflect real segment times."""
    first = straight_points((30.0, -97.0), (30.5, -97.0), 10)
    second = straight_points((30.5, -97.0), (31.0, -97.0), 10)[1:]
    slow, fast = make_route(first, mph=30), make_route([first[-1], *second], mph=60)
    route = make_route(first + second)
    route.cum_seconds = slow.cum_seconds + [slow.duration_s + s for s in fast.cum_seconds[1:]]

    halfway = route.distance_mi / 2
    _, seconds = route.position_at(halfway)
    assert seconds == pytest.approx(halfway / 30 * 3600, rel=1e-6)
