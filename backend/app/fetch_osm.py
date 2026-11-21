"""Download real road data once:   python -m app.fetch_osm            (Hubballi, 3 km radius)
Other place:                       python -m app.fetch_osm --lat 12.97 --lng 77.59 --km 3
If servers are busy, use a smaller area:  --km 2
Manual fallback: python -m app.fetch_osm --print-query   (paste the query into https://overpass-turbo.eu, Run, Export > raw OSM data (JSON),
                 save as raw.json, then:  python -m app.fetch_osm --file raw.json)"""

import argparse
import json
from . import osm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, default=15.3647)
    ap.add_argument("--lng", type=float, default=75.1240)
    ap.add_argument("--km", type=float, default=3.0)
    ap.add_argument("--file", help="use an Overpass JSON file you downloaded yourself")
    ap.add_argument("--print-query", action="store_true")
    ap.add_argument(
        "--compress",
        action="store_true",
        help="make osm_cache.json.gz from an existing download (needed for deployment)",
    )
    a = ap.parse_args()
    if a.compress:
        osm.compress()
        import os

        print(f"Wrote {osm.CACHE}.gz ({os.path.getsize(osm.CACHE + '.gz') // 1024} KB)")
        return
    if a.print_query:
        print(osm.query(osm.bbox(a.lat, a.lng, a.km)))
        return
    if a.file:
        raw = json.load(open(a.file, encoding="utf-8"))
        print(f"Using {a.file}")
    else:
        print(
            f"Downloading OpenStreetMap roads within {a.km} km of ({a.lat}, {a.lng}) ... this can take 1-2 minutes"
        )
        raw = osm.fetch(a.lat, a.lng, a.km)
    print(f"  got {len(raw['elements'])} map elements. Fetching elevation samples ...")
    data = {
        "center": [a.lat, a.lng],
        "km": a.km,
        "overpass": raw,
        "elev": osm.fetch_elev(osm.bbox(a.lat, a.lng, a.km)),
    }
    prof = osm.build_profile(data)  # validate before saving
    osm.save(data)
    G = prof["G"]
    print(f"Saved {osm.CACHE}\n  road nodes: {G.number_of_nodes()}  road segments: {G.number_of_edges()}")
    print("  wards:", ", ".join(prof["wards"]))
    print("  landmarks:", ", ".join(prof["landmarks"]))
    print("  bridges found:", len(prof["bridges"]), "| elevation:", "yes" if data["elev"] else "no")
    print("Done. Restart the backend to use the real map.")


if __name__ == "__main__":
    main()
