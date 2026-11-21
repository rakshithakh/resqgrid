"""Real OpenStreetMap roads. Download once with `python -m app.fetch_osm`; the data is cached on disk."""

from __future__ import annotations
import gzip
import json
import math
import os
import time
import urllib.parse
import urllib.request
import networkx as nx
from . import core

HW = {
    "trunk": 40,
    "trunk_link": 30,
    "primary": 35,
    "primary_link": 28,
    "secondary": 30,
    "secondary_link": 25,
    "tertiary": 28,
    "tertiary_link": 22,
    "unclassified": 22,
    "residential": 20,
    "living_street": 10,
}
PLACES = {"suburb", "neighbourhood", "quarter", "village", "hamlet", "town"}
CATS = {
    "hospital": "Civil Hospital",
    "bus_station": "Bus Stand",
    "marketplace": "Market Yard",
    "school": "Govt High School",
    "place_of_worship": "Temple Street",
}
CACHE = os.getenv(
    "OSM_CACHE",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "osm_cache.json"),
)
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]


def bbox(lat, lng, km):
    dlat = km / 111.32
    dlng = km / (111.32 * math.cos(math.radians(lat)))
    return (lat - dlat, lng - dlng, lat + dlat, lng + dlng)


def query(b):
    s, w, n, e = b
    box = f"({s},{w},{n},{e})"
    hw = "|".join(HW)
    return (
        f'[out:json][timeout:120];(way["highway"~"^({hw})$"]{box};'
        f'node["place"~"^({"|".join(PLACES)})$"]["name"]{box};'
        f'nwr["amenity"~"^({"|".join(CATS)})$"]["name"]{box};);out body;>;out skel qt;'
    )


def fetch(lat, lng, km):
    q = urllib.parse.urlencode({"data": query(bbox(lat, lng, km))}).encode()
    last = None
    for attempt in range(3):
        for url in ENDPOINTS:
            try:
                req = urllib.request.Request(url, data=q, headers={"User-Agent": "ResQGrid-hackathon/1.0"})
                with urllib.request.urlopen(req, timeout=150) as r:
                    return json.loads(r.read())
            except Exception as e:
                last = e
                print("  endpoint failed:", url, e)
        if attempt < 2:
            wait = 15 * (attempt + 1)
            print(f"  all servers busy, retrying in {wait}s (attempt {attempt + 2} of 3) ...")
            time.sleep(wait)
    raise RuntimeError(f"All Overpass servers failed: {last}")


def fetch_elev(b, n=12):
    """Coarse n x n elevation grid from Open-Meteo, used only to flag stranding claims made from high ground."""
    s, w, nn, e = b
    pts = [(s + (nn - s) * i / (n - 1), w + (e - w) * j / (n - 1)) for i in range(n) for j in range(n)]
    vals = []
    try:
        for k in range(0, len(pts), 72):
            ch = pts[k : k + 72]
            url = "https://api.open-meteo.com/v1/elevation?" + urllib.parse.urlencode(
                {
                    "latitude": ",".join(f"{p[0]:.5f}" for p in ch),
                    "longitude": ",".join(f"{p[1]:.5f}" for p in ch),
                }
            )
            with urllib.request.urlopen(url, timeout=30) as r:
                vals += json.loads(r.read())["elevation"]
        return {"bbox": list(b), "n": n, "values": vals}
    except Exception as ex:
        print("  elevation unavailable (high-ground check will be off):", ex)
        return None


def save(data):
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w") as f:
        json.dump(data, f)
    compress()


def compress():
    """Write a gzip copy of the map cache, small enough to commit to git."""
    with open(CACHE, "rb") as f, gzip.open(CACHE + ".gz", "wb") as g:
        g.write(f.read())


def load_profile():
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            return build_profile(json.load(f))
    if os.path.exists(CACHE + ".gz"):
        with gzip.open(CACHE + ".gz", "rt", encoding="utf-8") as f:
            return build_profile(json.load(f))
    return None


def _spread(cands, k, chosen, center):
    chosen = list(chosen)
    pool = [c for c in cands if all(c["node"] != x["node"] for x in chosen)]
    while pool and len(chosen) < k:
        if not chosen:
            nxt = min(pool, key=lambda c: core.hav((c["lat"], c["lng"]), center))
        else:
            nxt = max(
                pool, key=lambda c: min(core.hav((c["lat"], c["lng"]), (x["lat"], x["lng"])) for x in chosen)
            )
        chosen.append(nxt)
        pool.remove(nxt)
    return chosen


def build_profile(data):
    lat0, lng0 = data["center"]
    km = data["km"]
    center = (lat0, lng0)
    els = data["overpass"]["elements"]
    pos = {e["id"]: (e["lat"], e["lon"]) for e in els if e["type"] == "node" and "lat" in e}
    G = nx.Graph()
    bridges = []
    for w in (e for e in els if e["type"] == "way"):
        t = w.get("tags", {})
        hw = t.get("highway")
        if hw not in HW:
            continue
        nd = [n for n in w["nodes"] if n in pos]
        if len(nd) < 2:
            continue
        br = t.get("bridge") not in (None, "no")
        sp = HW[hw] / 3.6 * (0.8 if br else 1.0)
        total = 0.0
        for a, b in zip(nd, nd[1:]):
            L = core.hav(pos[a], pos[b])
            if L == 0:
                continue
            tm = L / sp
            if G.has_edge(a, b) and G[a][b]["time"] <= tm:
                continue
            G.add_edge(a, b, length=L, time=tm, bridge=br)
            total += L
        if br:
            bridges.append((total, nd))
    if G.number_of_nodes() < 20:
        raise ValueError("OSM cache has too few roads")
    G = G.subgraph(max(nx.connected_components(G), key=len)).copy()
    for n in G.nodes:
        G.nodes[n]["lat"], G.nodes[n]["lng"] = pos[n]
    ev = data.get("elev")
    thr = None
    if ev and len(ev["values"]) == ev["n"] ** 2:
        s, w, nn, e = ev["bbox"]
        n = ev["n"]
        lo, hi = min(ev["values"]), max(ev["values"])
        for node in G.nodes:
            la, lo_ = pos[node]
            i = min(n - 1, max(0, round((la - s) / (nn - s) * (n - 1))))
            j = min(n - 1, max(0, round((lo_ - w) / (e - w) * (n - 1))))
            G.nodes[node]["elev"] = ev["values"][i * n + j]
        if hi - lo >= 15:
            thr = lo + 0.85 * (hi - lo)
    nodes_ll = {n: (G.nodes[n]["lat"], G.nodes[n]["lng"]) for n in G.nodes}

    def nearest(la, lo_):
        k = math.cos(math.radians(la))
        return min(nodes_ll, key=lambda n: (nodes_ll[n][0] - la) ** 2 + ((nodes_ll[n][1] - lo_) * k) ** 2)

    def cand(name, la, lo_):
        n = nearest(la, lo_)
        return {"name": name, "node": n, "lat": nodes_ll[n][0], "lng": nodes_ll[n][1]}

    named, amen = [], {c: [] for c in CATS}
    for e in els:
        t = e.get("tags") or {}
        name = t.get("name")
        if not name:
            continue
        if e["type"] == "node" and t.get("place") in PLACES:
            named.append(cand(name, e["lat"], e["lon"]))
        elif t.get("amenity") in CATS:
            if e["type"] == "node":
                p = (e["lat"], e["lon"])
            elif e["type"] == "way":
                pts = [pos[n] for n in e.get("nodes", []) if n in pos]
                if not pts:
                    continue
                p = (sum(q[0] for q in pts) / len(pts), sum(q[1] for q in pts) / len(pts))
            else:
                continue
            amen[t["amenity"]].append(cand(name, *p))
    allnodes = list(G.nodes)
    step = max(1, len(allnodes) // 300)
    filler = [cand(None, *nodes_ll[n]) for n in allnodes[::step]]
    wards = _spread(named, 12, [], center)
    wards = _spread(filler, 12, wards, center)
    wards.sort(key=lambda c: (c["lng"], -c["lat"]))
    W, WN, WA = {}, {}, {}
    for i, c in enumerate(wards, 1):
        d = f"Ward {i} · {c['name']}" if c["name"] else f"Ward {i}"
        W[d] = c["node"]
        WN[i] = d
        if c["name"]:
            WA[d] = [c["name"]]
    used = [{"node": c["node"], "lat": c["lat"], "lng": c["lng"]} for c in wards]
    LM = {}
    for cat, generic in CATS.items():
        pool = sorted(amen[cat], key=lambda c: core.hav((c["lat"], c["lng"]), center))
        c = pool[0] if pool else _spread(filler, len(used) + 1, used, center)[-1]
        disp = c.get("name") or generic
        LM[disp] = (
            c["node"],
            core.LANDMARKS[generic][1] + [generic.lower()] + ([disp.lower()] if c.get("name") else []),
        )
        used.append(c)
    bridges.sort(key=lambda b: -b[0])
    good = [b for b in bridges if b[0] >= 30]
    if good:
        bn = good[0][1][len(good[0][1]) // 2]
    else:
        bn = _spread(filler, len(used) + 1, used, center)[-1]["node"]
    LM["Old Bridge Road"] = (bn, core.LANDMARKS["Old Bridge Road"][1])
    bl = [
        {
            "id": f"B{i}",
            "lat": nodes_ll[b[1][len(b[1]) // 2]][0],
            "lng": nodes_ll[b[1][len(b[1]) // 2]][1],
            "label": f"Bridge {i}",
        }
        for i, b in enumerate(good[:3], 1)
    ]
    dl = km / (111.32 * math.cos(math.radians(lat0)))
    d1, d2 = nearest(lat0, lng0 - 0.5 * dl), nearest(lat0, lng0 + 0.5 * dl)

    def high_ground(n):
        return thr is not None and G.nodes[n].get("elev", 0) >= thr

    return {
        "mode": "osm",
        "G": G,
        "center": center,
        "wards": W,
        "ward_nums": WN,
        "ward_alias": WA,
        "landmarks": LM,
        "depots": {"D1": {**core.DEPOT_T["D1"], "node": d1}, "D2": {**core.DEPOT_T["D2"], "node": d2}},
        "bridges": bl,
        "river": [],
        "roads": [],
        "tiles": True,
        "highground": high_ground,
        "service_m": km * 1300,
        "default_radius": 120,
        "radii": [60, 120, 250, 500],
    }
