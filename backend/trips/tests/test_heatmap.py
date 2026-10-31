from datetime import UTC, datetime

from trips.services.heatmap import HEATMAP_HOURS, build_grid, build_heatmap
from trips.services.weather import WeatherClient

from .fakes import straight_points

LINE = straight_points((32.7767, -96.797), (29.7604, -95.3698), 40)
DEPARTURE = datetime(2026, 11, 2, 14, 25, tzinfo=UTC)


def test_grid_respects_cell_budget():
    for budget in (40, 150):
        grid = build_grid([LINE], max_cells=budget)
        assert 0 < len(grid.cells) <= budget
        indexes = [grid.image_index(c, r) for c, r in grid.cells]
        assert len(set(indexes)) == len(indexes)
        assert all(0 <= i < grid.cols * grid.rows for i in indexes)


def test_bounds_contain_the_route():
    grid = build_grid([LINE], max_cells=150)
    (west, north), _, (east, south), _ = grid.bounds()
    for lat, lng in LINE:
        assert south < lat < north and west < lng < east


def test_heatmap_payload(providers):
    def weather(lat, lng, ts):  # wind ramps up hour by hour
        hour = (ts - int(DEPARTURE.timestamp()) // 3600 * 3600) // 3600
        return (min(10 + hour, 60), 0.0, 0.0, 0.0)

    providers.weather = weather
    client = WeatherClient(http=providers.client(), base_url="https://api.open-meteo.test", api_key="")
    heatmap = build_heatmap([LINE], DEPARTURE, 20_000, client, max_cells=60)

    assert heatmap["hours"] == HEATMAP_HOURS == len(heatmap["values"])
    assert heatmap["start"] == "2026-11-02T14:00:00Z"  # hour 0 = departure hour
    assert all(len(row) == len(heatmap["cells"]) for row in heatmap["values"])
    first, last = heatmap["values"][0][0], heatmap["values"][-1][0]
    assert first == 4  # 10 mph → 0.4 within the Low band, ×10
    assert last == 40  # 58 mph → No Travel
    assert providers.weather_locations == len(heatmap["cells"])
