from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from trips.exceptions import NoRouteError
from trips.models import TripPlan
from trips.services.routing import RoutingClient

pytestmark = pytest.mark.django_db

DALLAS = {"label": "Dallas, Texas, United States", "lat": 32.7767, "lng": -96.797}
HOUSTON = {"label": "Houston, Texas, United States", "lat": 29.7604, "lng": -95.3698}


@pytest.fixture
def api():
    return APIClient()


def payload(**overrides):
    body = {
        "origin": DALLAS,
        "destination": HOUSTON,
        "departure_at": (timezone.now() + timedelta(hours=2)).isoformat(),
        "load_weight_lb": 42_000,
        "interval_miles": 25,
    }
    body.update(overrides)
    return body


def create(api, **overrides):
    return api.post("/api/trip-plans/", payload(**overrides), format="json")


class TestCreateValidation:
    @pytest.mark.parametrize(
        "overrides, field",
        [
            ({"origin": ""}, "origin"),
            ({"origin": "x"}, "origin"),
            ({"origin": {"lat": 95, "lng": 0}}, "origin"),
            ({"origin": 42}, "origin"),
            ({"destination": DALLAS}, "destination"),
            ({"load_weight_lb": -1}, "load_weight_lb"),
            ({"load_weight_lb": 80_001}, "load_weight_lb"),
            ({"load_weight_lb": 12.5}, "load_weight_lb"),
            ({"interval_miles": 20}, "interval_miles"),
            ({"departure_at": "tomorrow"}, "departure_at"),
            ({"departure_at": (timezone.now() - timedelta(hours=2)).isoformat()}, "departure_at"),
            ({"departure_at": (timezone.now() + timedelta(days=8)).isoformat()}, "departure_at"),
        ],
    )
    def test_invalid_input_returns_400_with_field_error(self, api, providers, overrides, field):
        response = create(api, **overrides)
        assert response.status_code == 400
        assert field in response.json()
        assert providers.calls == {"osrm": 0, "photon": 0, "open-meteo": 0}

    def test_missing_fields(self, api, providers):
        response = api.post("/api/trip-plans/", {}, format="json")
        assert response.status_code == 400
        assert set(response.json()) == {"origin", "destination", "departure_at", "load_weight_lb", "interval_miles"}

    def test_unknown_place(self, api, providers):
        response = create(api, origin="Nowhere at all")
        assert response.status_code == 400
        assert response.json() == {"origin": ['No place found for "Nowhere at all".']}


class TestCreate:
    def test_creates_plan_with_three_ranked_routes(self, api, providers, django_assert_num_queries):
        with django_assert_num_queries(1):  # a single INSERT
            response = create(api, interval_miles=10)
        assert response.status_code == 201
        body = response.json()
        assert body["input"]["load_weight_lb"] == 42_000
        assert len(body["routes"]) == 3
        ids = [r["id"] for r in body["routes"]]
        assert ids == ["A", "B", "C"]
        assert sorted(r["rank"] for r in body["routes"]) == [1, 2, 3]
        rec = body["recommendation"]
        assert rec["route_id"] in ids and rec["ranking"][0] == rec["route_id"]
        assert [r["recommended"] for r in body["routes"]].count(True) == 1

        route = body["routes"][0]
        assert set(route["summary"]) == {"miles_by_risk", "average_risk", "max_risk", "no_travel"}
        assert sum(route["summary"]["miles_by_risk"].values()) == pytest.approx(route["distance_mi"], abs=0.3)
        cps = route["checkpoints"]
        assert cps[0]["mile"] == 0 and cps[1]["mile"] == 10
        assert [c["eta"] for c in cps] == sorted(c["eta"] for c in cps)
        assert {"lat", "lng", "eta", "wind_mph", "rain_in_hr", "snow_in_hr", "risk", "conditions"} <= set(cps[0])
        assert TripPlan.objects.count() == 1

    def test_free_text_places_are_geocoded(self, api, providers):
        response = create(api, origin="Dallas TX", destination="Houston TX")
        assert response.status_code == 201
        assert response.json()["input"]["origin"]["label"] == "Dallas, Texas, United States"
        assert providers.calls["photon"] == 2

    def test_load_rule_drives_the_recommendation(self, api, providers):
        # 40 mph everywhere: High for a light truck, Severe above 40,000 lb.
        providers.weather = lambda lat, lng, ts: (40.0, 0.0, 0.0, 0.0)
        light = create(api, load_weight_lb=30_000).json()
        heavy = create(api, load_weight_lb=45_000).json()
        assert {r["summary"]["max_risk"] for r in light["routes"]} == {"high"}
        assert {r["summary"]["max_risk"] for r in heavy["routes"]} == {"severe"}
        assert heavy["routes"][0]["checkpoints"][0]["load_adjusted"] is True

    def test_upstream_failure_returns_502(self, api, providers):
        providers.osrm_status = 500
        response = create(api)
        assert response.status_code == 502
        assert response.json()["code"] == "upstream_error"

    def test_no_drivable_route_returns_422(self, api, providers, monkeypatch):
        def no_route(*args, **kwargs):
            raise NoRouteError()

        monkeypatch.setattr(RoutingClient, "route", no_route)
        response = create(api)
        assert response.status_code == 422
        assert response.json()["code"] == "no_route"

    def test_weather_quota_returns_plan_with_degraded_note(self, api, providers):
        providers.weather_status = 429
        response = create(api)
        assert response.status_code == 201
        body = response.json()
        assert any("quota" in note.lower() for note in body["notes"])
        assert all(not cp["forecast_complete"] for route in body["routes"] for cp in route["checkpoints"])


class TestRetrieveAndHeatmap:
    def test_retrieve(self, api, providers, django_assert_num_queries):
        plan_id = create(api).json()["id"]
        with django_assert_num_queries(1):
            response = api.get(f"/api/trip-plans/{plan_id}/")
        assert response.status_code == 200
        assert response.json()["id"] == plan_id

    def test_retrieve_unknown_returns_404(self, api):
        response = api.get("/api/trip-plans/00000000-0000-0000-0000-000000000000/")
        assert response.status_code == 404
        assert response.json()["code"] == "not_found"

    def test_heatmap_is_computed_once_then_served_from_the_plan(
        self, api, providers, django_assert_num_queries, settings
    ):
        settings.HEATMAP_MAX_CELLS = 50
        plan_id = create(api).json()["id"]
        with django_assert_num_queries(2):  # SELECT + UPDATE
            first = api.get(f"/api/trip-plans/{plan_id}/heatmap/")
        assert first.status_code == 200
        body = first.json()
        assert body["hours"] == 49 and len(body["values"]) == 49
        assert 0 < len(body["cells"]) <= 50
        weather_calls = providers.calls["open-meteo"]

        with django_assert_num_queries(1):  # SELECT only
            second = api.get(f"/api/trip-plans/{plan_id}/heatmap/")
        assert second.json() == body
        assert providers.calls["open-meteo"] == weather_calls

    def test_heatmap_unknown_plan(self, api):
        assert api.get("/api/trip-plans/00000000-0000-0000-0000-000000000000/heatmap/").status_code == 404

    def test_list_and_delete_are_not_exposed(self, api):
        assert api.get("/api/trip-plans/").status_code == 405


class TestGeocode:
    def test_returns_suggestions_and_caches(self, api, providers):
        first = api.get("/api/geocode/", {"q": "Dallas"})
        assert first.status_code == 200
        assert first.json()["results"][0] == {"label": "Dallas, Texas, United States", "lat": 32.7767, "lng": -96.797}
        api.get("/api/geocode/", {"q": "dallas"})
        assert providers.calls["photon"] == 1

    @pytest.mark.parametrize("params", [{}, {"q": "ab"}, {"q": "x" * 201}])
    def test_validates_query(self, api, providers, params):
        assert api.get("/api/geocode/", params).status_code == 400
        assert providers.calls["photon"] == 0
