from datetime import UTC, datetime

import pytest

from trips.exceptions import UpstreamError
from trips.services.weather import (
    DAY,
    HOUR,
    Forecast,
    Hourly,
    WeatherClient,
    forecast_windows,
    plan_locations,
    to_cell,
)

from .fakes import FakeProviders

T0 = int(datetime(2026, 11, 2, 14, 0, tzinfo=UTC).timestamp())
POINT = (35.0, -97.0)


def forecast_with(hours: dict[int, Hourly]) -> Forecast:
    return Forecast({to_cell(POINT, 0.05): hours})


class TestTimeSemantics:
    def test_wind_is_interpolated_between_hours(self):
        fc = forecast_with({T0: Hourly(20, 0, 0), T0 + HOUR: Hourly(40, 0, 0)})
        assert fc.conditions(POINT, T0 + 15 * 60).wind_mph == pytest.approx(25.0)

    def test_precipitation_comes_from_the_hour_being_driven_through(self):
        # Stamp T0+1h holds the total for (T0, T0+1h] — the hour containing an ETA of T0+20min.
        fc = forecast_with({T0: Hourly(10, 0.9, 3.5), T0 + HOUR: Hourly(10, 0.3, 0.6)})
        cond = fc.conditions(POINT, T0 + 20 * 60)
        assert (cond.rain_in_hr, cond.snow_in_hr) == (0.3, 0.6)

    def test_on_the_hour_uses_that_hours_wind_and_next_bucket(self):
        fc = forecast_with({T0: Hourly(31, 0.0, 0), T0 + HOUR: Hourly(99, 0.2, 0)})
        cond = fc.conditions(POINT, T0)
        assert cond.wind_mph == 31 and cond.rain_in_hr == 0.2

    def test_missing_data_is_flagged(self):
        cond = forecast_with({}).conditions(POINT, T0)
        assert cond.complete is False
        assert (cond.wind_mph, cond.rain_in_hr, cond.snow_in_hr) == (0, 0, 0)


def test_windows_start_at_the_utc_day_and_use_fixed_tiers():
    now = T0
    windows = forecast_windows([T0 + 5 * HOUR, T0 + 30 * HOUR], now=now)
    day = T0 // DAY * DAY
    assert windows[0] == (day, day + 3 * DAY - HOUR)
    assert [w[1] - w[0] for w in windows] == [3 * DAY - HOUR, 6 * DAY - HOUR, 10 * DAY - HOUR]
    # A need beyond 3 days skips the smallest tier.
    assert forecast_windows([T0 + 4 * DAY], now=now)[0] == (day, day + 6 * DAY - HOUR)


def test_location_budget_coarsens_the_lattice():
    points = [((30 + i * 0.15, -97.0), T0) for i in range(100)]  # ~10 mi apart
    fine_deg, fine = plan_locations(points, max_locations=1000)
    coarse_deg, coarse = plan_locations(points, max_locations=40)
    assert (fine_deg, len(fine)) == (0.05, 100)
    assert coarse_deg > fine_deg and len(coarse) <= 40


class TestClient:
    def make(self, providers):
        return WeatherClient(http=providers.client(), base_url="https://api.open-meteo.test", api_key="")

    def test_batches_dedupes_and_caches(self, providers):
        providers.weather = lambda lat, lng, ts: (30.0, 0.1, 0.05, 0.0)
        client = self.make(providers)
        # 120 distinct cells + duplicates that snap to the same cells.
        pts = [((30 + i * 0.1, -97.0), T0) for i in range(120)] + [((30.001, -97.001), T0)]
        fc = client.forecast(pts, max_locations=500, now=T0)
        assert providers.calls["open-meteo"] == 3  # 50 + 50 + 20 locations
        assert providers.weather_locations == 120
        cond = fc.conditions((30.0, -97.0), T0 + 600)
        assert cond.wind_mph == 30.0 and cond.rain_in_hr == pytest.approx(0.15) and cond.complete

        # Same cells, different departure the same day → served from cache, no new calls.
        client.forecast([(p, ts + 6 * HOUR) for p, ts in pts], max_locations=500, now=T0)
        assert providers.calls["open-meteo"] == 3

    def test_quota_error_becomes_503(self, providers):
        providers.weather_status = 429
        with pytest.raises(UpstreamError) as exc:
            self.make(providers).forecast([(POINT, T0)], max_locations=10, now=T0)
        assert exc.value.status_code == 503
