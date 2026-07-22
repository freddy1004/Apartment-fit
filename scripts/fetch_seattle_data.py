#!/usr/bin/env python3
"""Refresh Seattle open-data caches (crime, elevation) from live sources.

Run when you have network access to the public open-data endpoints:

    cd backend && python ../scripts/fetch_seattle_data.py

Writes:
- backend/app/data/cache/crime_live.json   (SPD incidents -> choropleth)
- prints refreshed elevation samples you can paste into seattle_real.py

Everything degrades gracefully offline: if a source is unreachable, the app
keeps using the bundled real-Seattle-grounded reference data.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.data import seattle_real as R  # noqa: E402
from app.data import open_data as od  # noqa: E402

BBOX = [-122.42, 47.60, -122.27, 47.73]


def main() -> int:
    ok = True
    try:
        layer = od.build_live_crime_layer(BBOX)
        n = len(layer.features["features"])
        print(f"[crime]     wrote {n} grid cells from live SPD data -> cache/crime_live.json")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"[crime]     skipped (source unreachable): {e}")

    try:
        pts = [(la, lo) for (_n, la, lo, _v) in R.NEIGHBORHOOD_CRIME]
        elevs = od.fetch_elevations(pts[:10])
        print(f"[elevation] fetched {len([e for e in elevs if e is not None])} live samples")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"[elevation] skipped (source unreachable): {e}")

    print("Done." if ok else "Done (some sources unreachable; bundled data still in use).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
