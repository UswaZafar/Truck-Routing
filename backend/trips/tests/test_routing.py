import pytest

from trips.exceptions import NoRouteError, UpstreamError
from trips.services.geo import decode_polyline
from trips.services.routing import (
    RELAXED,
    STRICT,
    RoutingClient,
    backtrack_ratio,
    overlap_ratio,
    parse_osrm_route,
    pick_detours,
)

from .fakes import encode_polyline, make_route, osrm_route_json, straight_points

DALLAS, HOUSTON = (32.7767, -96.797), (29.7604, -95.3698)


def test_polyline_round_trip():
    pts = [(32.7767, -96.797), (31.5, -95.2), (29.7604, -95.3698)]
    decoded = decode_polyline(encode_polyline(pts))
    assert [c for p in decoded for c in p] == pytest.approx([c for p in pts for c in p])


def test_parse_scales_annotation_durations_to_leg_total():
    data = osrm_route_json([DALLAS, HOUSTON], mph=60)
    data["legs"][0]["duration"] *= 1.1  # turn penalties are in the leg total, not the annotations
    route = parse_osrm_route(data, "osrm")
    assert route.duration_s == pytest.approx(data["legs"][0]["duration"])
    assert route.distance_mi == pytest.approx(make_route(route.points).distance_mi)


def test_overlap_and_backtrack():
    base = make_route(straight_points(DALLAS, HOUSTON, 50))
    same = make_route(straight_points(DALLAS, HOUSTON, 80))
    detour = make_route(straight_points(DALLAS, (31.3, -94.5), 30) + straight_points((31.3, -94.5), HOUSTON, 30)[1:])
    there_and_back = make_route(
        straight_points(DALLAS, (31.3, -96.0), 30)
        + straight_points((31.3, -96.0), (31.3, -94.5), 20)[1:]
        + straight_points((31.3, -94.5), (31.3, -96.0), 20)[1:]
        + straight_points((31.3, -96.0), HOUSTON, 30)[1:]
    )
    assert overlap_ratio(same, base) > 0.95
    assert overlap_ratio(detour, base) < 0.2
    assert backtrack_ratio(detour) == 0
    assert backtrack_ratio(there_and_back) > 0.2


def test_pick_detours_applies_limits():
    fastest = make_route(straight_points(DALLAS, HOUSTON, 50), mph=60)
    slow = make_route(straight_points(DALLAS, (31.3, -94.0), 30) + straight_points((31.3, -94.0), HOUSTON, 30)[1:], mph=25)
    distinct = make_route(straight_points(DALLAS, (31.3, -94.9), 30) + straight_points((31.3, -94.9), HOUSTON, 30)[1:], mph=60)
    assert pick_detours([fastest], [slow, distinct], 2, STRICT) == [distinct]
    assert pick_detours([fastest], [slow], 1, RELAXED) == []  # >2× slower is never offered
    assert pick_detours([fastest], [fastest], 1, RELAXED) == []  # identical to a kept route


class TestFindRoutes:
    def test_tops_up_to_three_distinct_routes_with_detours(self, providers):
        providers.osrm_routes = 1
        routes = RoutingClient().find_routes(DALLAS, HOUSTON)
        assert len(routes) == 3
        assert routes[0].source == "osrm"
        assert {r.source for r in routes[1:]} == {"osrm-via"}
        assert [r.duration_s for r in routes] == sorted(r.duration_s for r in routes)
        for i, a in enumerate(routes):
            for b in routes[i + 1 :]:
                assert overlap_ratio(b, a) <= RELAXED.max_overlap

    def test_uses_osrm_alternatives_when_available_and_caches(self, providers):
        providers.osrm_routes = 3
        client = RoutingClient()
        routes = client.find_routes(DALLAS, HOUSTON)
        assert [r.source for r in routes] == ["osrm"] * 3
        calls = providers.calls["osrm"]
        assert client.find_routes(DALLAS, HOUSTON) == routes
        assert providers.calls["osrm"] == calls

    def test_no_route(self, providers, monkeypatch):
        client = RoutingClient()
        monkeypatch.setattr(client, "route", lambda *a, **k: (_ for _ in ()).throw(NoRouteError()))
        with pytest.raises(NoRouteError):
            client.find_routes(DALLAS, HOUSTON)

    def test_upstream_failure(self, providers):
        providers.osrm_status = 500
        with pytest.raises(UpstreamError):
            RoutingClient().find_routes(DALLAS, HOUSTON)
