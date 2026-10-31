"""Every threshold edge from the assessment's risk and load tables."""

import math

import pytest

from trips.services.risk import RiskLevel, assess, rain_level, risk_index, snow_level, wind_level

L, M, H, S, N = RiskLevel.LOW, RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.SEVERE, RiskLevel.NO_TRAVEL


@pytest.mark.parametrize(
    "mph, expected",
    [(0, L), (24.9, L), (25, M), (34, M), (34.9, M), (35, H), (44, H), (44.9, H), (45, S), (54, S), (54.9, S), (55, N), (80, N)],
)
def test_wind_bands_light_load(mph, expected):
    assert wind_level(mph, load_weight_lb=10_000) == expected


@pytest.mark.parametrize(
    "rain, expected",
    [(0, L), (0.099, L), (0.10, M), (0.249, M), (0.25, H), (0.499, H), (0.50, S), (1.00, S), (1.001, N), (2.5, N)],
)
def test_rain_bands(rain, expected):
    assert rain_level(rain) == expected


@pytest.mark.parametrize(
    "snow, expected",
    [(0, L), (0.49, L), (0.5, M), (0.99, M), (1.0, H), (1.99, H), (2.0, S), (3.0, S), (3.01, N), (5, N)],
)
def test_snow_bands(snow, expected):
    assert snow_level(snow) == expected


class TestLoadRules:
    def test_55_mph_is_no_travel_for_any_load(self):
        assert wind_level(55, 0) == N
        assert wind_level(55, 80_000) == N

    @pytest.mark.parametrize("load, expected", [(30_000, S), (30_001, N), (45_000, N)])
    def test_45_to_54_mph_over_30000_lb_is_no_travel(self, load, expected):
        assert wind_level(45, load) == expected
        assert wind_level(54.9, load) == expected

    @pytest.mark.parametrize("load, expected", [(40_000, H), (40_001, S), (80_000, S)])
    def test_35_to_44_mph_over_40000_lb_is_severe(self, load, expected):
        assert wind_level(35, load) == expected
        assert wind_level(44.9, load) == expected

    def test_load_does_not_change_lower_wind_bands(self):
        assert wind_level(34.9, 80_000) == M
        assert wind_level(10, 80_000) == L


class TestAssess:
    def test_worst_condition_wins_and_is_reported(self):
        result = assess(wind_mph=20, rain_in_hr=0.3, snow_in_hr=0.6, load_weight_lb=10_000)
        assert result.level == H
        assert result.conditions == ("rain",)

    def test_ties_report_every_condition(self):
        result = assess(wind_mph=30, rain_in_hr=0.15, snow_in_hr=0, load_weight_lb=0)
        assert result.level == M
        assert result.conditions == ("wind", "rain")

    def test_load_adjusted_flag(self):
        result = assess(wind_mph=40, rain_in_hr=0, snow_in_hr=0, load_weight_lb=42_000)
        assert result.level == S
        assert result.conditions == ("wind",)
        assert result.load_adjusted is True

    def test_calm_weather_has_no_conditions(self):
        result = assess(wind_mph=5, rain_in_hr=0, snow_in_hr=0, load_weight_lb=42_000)
        assert result.level == L
        assert result.conditions == ()
        assert result.load_adjusted is False


@pytest.mark.parametrize(
    "wind, rain, snow, load",
    [
        (0, 0, 0, 0),
        (12.5, 0.05, 0.2, 10_000),
        (30, 0.12, 0, 10_000),
        (40, 0, 0, 45_000),
        (47, 0, 0, 35_000),
        (47, 0, 0, 20_000),
        (20, 0.6, 2.4, 0),
        (60, 1.5, 4, 0),
        (24.99, 0.0999, 0.499, 0),
    ],
)
def test_risk_index_integer_part_matches_discrete_level(wind, rain, snow, load):
    index = risk_index(wind, rain, snow, load)
    assert 0 <= index <= 4
    assert math.floor(index) == assess(wind, rain, snow, load).level


def test_risk_index_grows_within_a_band():
    assert risk_index(10, 0, 0, 0) < risk_index(20, 0, 0, 0) < risk_index(25, 0, 0, 0)
