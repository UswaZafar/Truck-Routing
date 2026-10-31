"""Run the planning pipeline against the real providers (uses live API quota).

    python scripts/smoke_live.py [number_of_trips] [interval_miles]
"""

import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402

from trips.services.heatmap import build_heatmap  # noqa: E402
from trips.services.planner import compute_plan  # noqa: E402
from trips.services.weather import WeatherClient  # noqa: E402

TRIPS = [
    ("Dallas, TX", (32.7767, -96.7970), "Houston, TX", (29.7604, -95.3698)),
    ("Chicago, IL", (41.8781, -87.6298), "Denver, CO", (39.7392, -104.9903)),
    ("Los Angeles, CA", (34.0522, -118.2437), "New York, NY", (40.7128, -74.0060)),
]
LOAD_LB = 42_000


def main() -> None:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else len(TRIPS)
    interval = int(sys.argv[2]) if len(sys.argv) > 2 else 25
    departure = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)
    for origin_label, origin, dest_label, dest in TRIPS[:count]:
        started = time.perf_counter()
        plan = compute_plan(
            {"label": origin_label, "lat": origin[0], "lng": origin[1]},
            {"label": dest_label, "lat": dest[0], "lng": dest[1]},
            departure,
            LOAD_LB,
            interval,
        )
        print(f"\n{origin_label} → {dest_label}: {time.perf_counter() - started:.2f}s")
        print(f"  {plan['recommendation']['explanation']}")
        for route in plan["routes"]:
            cps = route["checkpoints"]
            monotonic = all(a["eta"] <= b["eta"] for a, b in zip(cps, cps[1:]))
            print(
                f"  {route['id']} #{route['rank']} {route['source']:8} {route['distance_mi']:7.1f} mi "
                f"{route['duration_s'] / 3600:5.1f} h  checkpoints={len(cps)} ETAs ordered={monotonic} "
                f"miles={route['summary']['miles_by_risk']}"
            )
        started = time.perf_counter()
        lines = [[(lat, lng) for lng, lat in route["geometry"]] for route in plan["routes"]]
        heatmap = build_heatmap(lines, departure, LOAD_LB, WeatherClient(), settings.HEATMAP_MAX_CELLS)
        print(f"  heatmap {time.perf_counter() - started:.2f}s, {len(heatmap['cells'])} cells; notes={plan['notes']}")


if __name__ == "__main__":
    main()
