"""Road graph (OpenStreetMap or the demo grid), place matching, hazard-aware routing and the dispatch solver.

Routing and allocation are plain algorithms. No LLM is involved in them.
"""

from __future__ import annotations
import math
import os
import random
import re
import networkx as nx

CENTER = (15.3647, 75.1240)  # Hubballi, used by the synthetic fallback grid
N = 14
DLAT, DLNG = 0.0040, 0.0043
BRIDGE_ROWS = (2, 7, 11)
RIVER_AFTER_COL = 6
SPEED = 8.3  # m/s (~30 km/h), synthetic grid
SERVICE_S = 300  # unloading time per stop
KG = {"water": 3.0, "food": 1.0, "medical": 0.5, "shelter": 2.0, "rescue": 0.5, "other": 1.0}
TYPEW = {"rescue": 2.0, "medical": 1.6, "water": 1.2, "food": 1.0, "shelter": 0.8, "other": 1.0}

WARDS = {
    1: (1, 1),
    2: (2, 4),
    3: (4, 1),
    4: (4, 5),
    5: (7, 3),
    6: (9, 1),
    7: (10, 5),
    8: (2, 9),
    9: (4, 12),
    10: (6, 8),
    11: (9, 10),
    12: (11, 12),
}
LANDMARKS = {
    "Civil Hospital": ((6, 4), ["civil hospital", "hospital", "अस्पताल", "ಆಸ್ಪತ್ರೆ"]),
    "Market Yard": ((8, 8), ["market yard", "mandi", "मंडी", "ಮಾರುಕಟ್ಟೆ"]),
    "Old Bridge Road": ((7, 6), ["old bridge", "bridge road", "पुल"]),
    "Govt High School": ((3, 10), ["high school", "govt school", "स्कूल", "ಶಾಲೆ"]),
    "Temple Street": ((11, 3), ["temple street", "mandir", "मंदिर", "ದೇವಸ್ಥಾನ"]),
    "Bus Stand": ((5, 9), ["bus stand", "bus stop", "बस स्टैंड", "ಬಸ್ ನಿಲ್ದಾಣ"]),
}
DEPOT_T = {
    "D1": {
        "id": "D1",
        "name": "West Relief Depot",
        "stock": {"water": 2600, "food": 1500, "medical": 380, "shelter": 500, "rescue": 300},
    },
    "D2": {
        "id": "D2",
        "name": "East Relief Depot",
        "stock": {"water": 420, "food": 900, "medical": 60, "shelter": 300, "rescue": 200},
    },
}
VEHICLES = [
    {"id": "W-01", "name": "Truck W-01", "depot_id": "D1", "capacity_kg": 600},
    {"id": "W-02", "name": "Truck W-02", "depot_id": "D1", "capacity_kg": 600},
    {"id": "W-03", "name": "Mini-truck W-03", "depot_id": "D1", "capacity_kg": 350},
    {"id": "E-01", "name": "Truck E-01", "depot_id": "D2", "capacity_kg": 600},
    {"id": "E-02", "name": "Mini-truck E-02", "depot_id": "D2", "capacity_kg": 350},
]
WARD_RE = r"(?:ward|wd|वार्ड|ವಾರ್ಡ್)\s*(?:no\.?|number|नंबर)?\s*[-#:]?\s*(\d{1,2})"
MAP: dict = {}


def hav(a, b):
    R = 6371000
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(x))


def seg_dist(p, a, b):
    k = 111320.0
    c = math.cos(math.radians(p[0]))

    def xy(q):
        return ((q[1] - p[1]) * k * c, (q[0] - p[0]) * k)

    ax, ay = xy(a)
    bx, by = xy(b)
    dx, dy = bx - ax, by - ay
    t = max(0, min(1, -(ax * dx + ay * dy) / ((dx * dx + dy * dy) or 1)))
    return math.hypot(ax + t * dx, ay + t * dy)


def coords(G, n):
    return (G.nodes[n]["lat"], G.nodes[n]["lng"])


def node_key(n):
    return f"{n[0]},{n[1]}" if isinstance(n, tuple) else str(n)


def parse_node(s):
    return tuple(int(i) for i in s.split(",")) if "," in s else int(s)


def build_graph():
    rnd = random.Random(11)
    G = nx.Graph()
    for r in range(N):
        for c in range(N):
            G.add_node(
                (r, c),
                lat=CENTER[0] - (r - (N - 1) / 2) * DLAT + rnd.uniform(-0.0005, 0.0005),
                lng=CENTER[1] + (c - (N - 1) / 2) * DLNG + rnd.uniform(-0.0005, 0.0005),
                elev=575 + 4 * abs(c - 6.5),
            )

    def add(u, v, bridge=False):
        L = hav(coords(G, u), coords(G, v))
        G.add_edge(u, v, length=L, time=L / (SPEED * (0.6 if bridge else 1)), bridge=bridge)

    for r in range(N):
        for c in range(N):
            if c + 1 < N:
                if c == RIVER_AFTER_COL:
                    if r in BRIDGE_ROWS:
                        add((r, c), (r, c + 1), True)
                else:
                    add((r, c), (r, c + 1))
            if r + 1 < N:
                add((r, c), (r + 1, c))
    local = [e for e in G.edges if not G.edges[e]["bridge"]]
    rnd.shuffle(local)
    for u, v in local[: int(len(local) * 0.08)]:
        d = dict(G.edges[u, v])
        G.remove_edge(u, v)
        if not nx.is_connected(G):
            G.add_edge(u, v, **d)
    return G


def synthetic_profile():
    G = build_graph()
    wards = {f"Ward {w}": node for w, node in WARDS.items()}
    bridges = []
    for u, v, d in G.edges(data=True):
        if d["bridge"]:
            a, b = coords(G, u), coords(G, v)
            bridges.append({"id": f"B{u[0]}", "lat": (a[0] + b[0]) / 2, "lng": (a[1] + b[1]) / 2})
    bridges.sort(key=lambda b: -b["lat"])
    for i, b in enumerate(bridges, 1):
        b["label"] = f"Bridge {i}"
    top, bot = CENTER[0] + DLAT * 7.5, CENTER[0] - DLAT * 7.5
    return {
        "mode": "synthetic",
        "G": G,
        "center": CENTER,
        "wards": wards,
        "ward_nums": {w: f"Ward {w}" for w in WARDS},
        "ward_alias": {},
        "landmarks": {n: (node, al) for n, (node, al) in LANDMARKS.items()},
        "depots": {"D1": {**DEPOT_T["D1"], "node": (6, 2)}, "D2": {**DEPOT_T["D2"], "node": (6, 11)}},
        "bridges": bridges,
        "river": [[top + (bot - top) * i / 24, CENTER[1] + 0.0003 * math.sin(i / 3)] for i in range(25)],
        "roads": [
            [list(coords(G, u)), list(coords(G, v)), bool(d["bridge"])] for u, v, d in G.edges(data=True)
        ],
        "tiles": False,
        "highground": lambda n: G.nodes[n]["elev"] >= 594,
        "service_m": 4500,
        "default_radius": 350,
        "radii": [200, 350, 600, 900],
    }


def finish_profile(p):
    G = p["G"]
    al = []
    for disp, (node, aliases) in p["landmarks"].items():
        for a in aliases + [disp.lower()]:
            al.append((a.lower(), disp, node))
    for disp, names in p["ward_alias"].items():
        for a in names:
            al.append((a.lower(), disp, p["wards"][disp]))
    p["aliases"] = al
    p["places"] = [
        {"name": d, "lat": coords(G, n)[0], "lng": coords(G, n)[1]} for d, n in p["wards"].items()
    ] + [{"name": d, "lat": coords(G, n)[0], "lng": coords(G, n)[1]} for d, (n, _) in p["landmarks"].items()]
    p["_n"] = list(G.nodes)
    p["_la"] = [G.nodes[n]["lat"] for n in p["_n"]]
    p["_lo"] = [G.nodes[n]["lng"] for n in p["_n"]]
    p["bounds"] = [[min(p["_la"]), min(p["_lo"])], [max(p["_la"]), max(p["_lo"])]]
    return p


def init():
    global MAP
    prof = None
    mode = os.getenv("MAP_MODE", "auto")
    if mode in ("auto", "osm"):
        try:
            from . import osm

            prof = osm.load_profile()
            if prof is None and mode == "osm":
                print("[map] MAP_MODE=osm but no cache found. Run: python -m app.fetch_osm")
        except Exception as e:
            print("[map] OSM data could not be loaded, using synthetic grid:", e)
    MAP = finish_profile(prof or synthetic_profile())
    print(f"[map] mode={MAP['mode']} nodes={MAP['G'].number_of_nodes()} edges={MAP['G'].number_of_edges()}")
    return MAP


def snap(lat, lng):
    """Closest road node to a GPS point, plus the distance to it in metres."""
    k = math.cos(math.radians(lat))
    best = None
    for n, la, lo in zip(MAP["_n"], MAP["_la"], MAP["_lo"]):
        d = (la - lat) ** 2 + ((lo - lng) * k) ** 2
        if best is None or d < best[0]:
            best = (d, n)
    return best[1], hav((lat, lng), coords(MAP["G"], best[1]))


def nearest_label(node):
    pt = coords(MAP["G"], node)
    best = min(MAP["places"], key=lambda q: hav(pt, (q["lat"], q["lng"])))
    return f"Near {best['name']}" if hav(pt, (best["lat"], best["lng"])) <= 1200 else "GPS location"


def match_place(text):
    t = text.lower()
    m = re.search(WARD_RE, t)
    if m and int(m.group(1)) in MAP["ward_nums"]:
        d = MAP["ward_nums"][int(m.group(1))]
        return d, MAP["wards"][d]
    best = None
    for a, disp, node in MAP["aliases"]:
        if a in t and (best is None or len(a) > best[0]):
            best = (len(a), disp, node)
    return (best[1], best[2]) if best else None


def map_geometry():
    return {
        "roads": MAP["roads"],
        "bridges": MAP["bridges"],
        "river": MAP["river"],
        "places": MAP["places"],
        "tiles": MAP["tiles"],
        "mode": MAP["mode"],
        "bounds": MAP["bounds"],
        "center": list(MAP["center"]),
        "default_radius": MAP["default_radius"],
        "radii": MAP["radii"],
    }


def edge_mult(G, hazards):
    m = {}
    for u, v in G.edges:
        a, b = coords(G, u), coords(G, v)
        for h in hazards:
            if seg_dist((h["lat"], h["lng"]), a, b) <= h["radius"]:
                f = math.inf if h["kind"] == "blocked" else 3.0
                k = frozenset((u, v))
                m[k] = max(m.get(k, 1), f)
    return m


def tables(G, mult, sources):
    def w(u, v, d):
        f = mult.get(frozenset((u, v)), 1)
        return None if f == math.inf else d["time"] * f

    return {s: nx.single_source_dijkstra(G, s, weight=w) for s in set(sources)}


def baseline_assign(vehicles, depots, needs):
    """Naive dispatch used for comparison: first come, first served, nearest truck by straight line."""
    load = {v["id"]: 0 for v in vehicles}
    pos = {v["id"]: depots[v["depot_id"]]["pos"] for v in vehicles}
    out = {v["id"]: [] for v in vehicles}
    for n in sorted(needs, key=lambda n: n["first_at"]):
        c = [v for v in vehicles if load[v["id"]] + n["demand_kg"] <= v["capacity_kg"]]
        if not c:
            continue
        v = min(c, key=lambda v: hav(pos[v["id"]], n["pos"]))
        out[v["id"]].append(n["id"])
        load[v["id"]] += n["demand_kg"]
        pos[v["id"]] = n["pos"]
    return out


def greedy_priority(tab, vehicles, depots, needs):
    load = {v["id"]: 0 for v in vehicles}
    cur = {v["id"]: depots[v["depot_id"]]["node"] for v in vehicles}
    out = {v["id"]: [] for v in vehicles}
    for n in sorted(needs, key=lambda n: -n["priority"]):
        best = None
        for v in vehicles:
            if load[v["id"]] + n["demand_kg"] > v["capacity_kg"]:
                continue
            d = tab[cur[v["id"]]][0].get(n["node"])
            if d is not None and (best is None or d < best[0]):
                best = (d, v)
        if best:
            v = best[1]
            out[v["id"]].append(n["id"])
            load[v["id"]] += n["demand_kg"]
            cur[v["id"]] = n["node"]
    return out


def optimized_assign(tab, vehicles, depots, needs):
    """Capacitated multi-depot routing with OR-Tools. Skipping a need costs more the higher its priority."""
    reach = [n for n in needs if any(n["node"] in tab[depots[v["depot_id"]]["node"]][0] for v in vehicles)]
    empty = {v["id"]: [] for v in vehicles}
    if not reach:
        return empty, "none"
    try:
        from ortools.constraint_solver import pywrapcp, routing_enums_pb2 as enums
    except ImportError:
        return greedy_priority(tab, vehicles, depots, reach), "greedy-priority"
    dep_ids = sorted({v["depot_id"] for v in vehicles})
    nodes = [depots[d]["node"] for d in dep_ids] + [n["node"] for n in reach]
    K, D, BIG = len(nodes), len(dep_ids), 10**7

    def cost(i, j):
        d = tab[nodes[i]][0].get(nodes[j])
        return BIG if d is None else int(d) + (SERVICE_S if i >= D else 0)

    M = [[cost(i, j) for j in range(K)] for i in range(K)]
    starts = [dep_ids.index(v["depot_id"]) for v in vehicles]
    mgr = pywrapcp.RoutingIndexManager(K, len(vehicles), starts, starts)
    rt = pywrapcp.RoutingModel(mgr)
    tcb = rt.RegisterTransitCallback(lambda i, j: M[mgr.IndexToNode(i)][mgr.IndexToNode(j)])
    rt.SetArcCostEvaluatorOfAllVehicles(tcb)
    dem = [0] * D + [max(1, int(n["demand_kg"])) for n in reach]
    dcb = rt.RegisterUnaryTransitCallback(lambda i: dem[mgr.IndexToNode(i)])
    rt.AddDimensionWithVehicleCapacity(dcb, 0, [int(v["capacity_kg"]) for v in vehicles], True, "Cap")
    rt.AddDimension(tcb, 0, 86400, True, "Time")
    td = rt.GetDimensionOrDie("Time")
    for k, n in enumerate(reach):
        idx = mgr.NodeToIndex(D + k)
        rt.AddDisjunction([idx], int(n["priority"] * 400) + 2000)
        td.SetCumulVarSoftUpperBound(idx, 0, int(n["priority"] // 20) + 1)
    p = pywrapcp.DefaultRoutingSearchParameters()
    p.first_solution_strategy = enums.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    p.local_search_metaheuristic = enums.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    p.time_limit.seconds = 1
    sol = rt.SolveWithParameters(p)
    if not sol:
        return greedy_priority(tab, vehicles, depots, reach), "greedy-priority"
    out = {}
    for vi, v in enumerate(vehicles):
        idx, seq = rt.Start(vi), []
        while not rt.IsEnd(idx):
            node = mgr.IndexToNode(idx)
            if node >= D:
                seq.append(reach[node - D]["id"])
            idx = sol.Value(rt.NextVar(idx))
        out[v["id"]] = seq
    return out, "ortools-cvrp"


def evaluate(G, tab, vehicles, depots, needs, assign):
    nmap = {n["id"]: n for n in needs}
    routes, served = [], set()
    for v in vehicles:
        start = depots[v["depot_id"]]["node"]
        cur, t, pts, times, stops, load = start, 0.0, [], [], [], 0.0
        for nid in assign.get(v["id"], []):
            n = nmap[nid]
            d, paths = tab[cur]
            if n["node"] not in d:
                continue  # unreachable under current hazards
            path = paths[n["node"]]
            for i, x in enumerate(path):
                if pts and i == 0:
                    continue
                pts.append(list(coords(G, x)))
                times.append(round(t + d[x], 1))
            t += d[n["node"]]
            stops.append(
                {
                    "need_id": nid,
                    "eta_s": round(t),
                    "label": n["label"],
                    "people": n["people"],
                    "types": n["types"],
                }
            )
            served.add(nid)
            load += n["demand_kg"]
            t += SERVICE_S
            pts.append(list(coords(G, n["node"])))
            times.append(round(t, 1))
            cur = n["node"]
        if stops:
            back = tab[cur][0].get(start, 0)
            routes.append(
                {
                    "vehicle_id": v["id"],
                    "depot_id": v["depot_id"],
                    "points": pts,
                    "times": times,
                    "stops": stops,
                    "load_kg": round(load),
                    "total_s": round(t + back),
                }
            )
    hp = [n for n in needs if n["priority"] >= 40]
    sv = [n for n in needs if n["id"] in served]
    eta = {s["need_id"]: s["eta_s"] for r in routes for s in r["stops"]}
    wp = sum(n["priority"] for n in sv) or 1
    metrics = {
        "needs_total": len(needs),
        "needs_served": len(sv),
        "unserved_ids": [n["id"] for n in needs if n["id"] not in served],
        "people_total": sum(n["people"] for n in needs),
        "people_reached": sum(n["people"] for n in sv),
        "high_priority_total": len(hp),
        "high_priority_served": sum(1 for n in hp if n["id"] in served),
        "avg_eta_high_min": round(
            sum(eta[n["id"]] for n in hp if n["id"] in eta)
            / max(1, sum(1 for n in hp if n["id"] in eta))
            / 60,
            1,
        ),
        "weighted_eta_min": round(sum(n["priority"] * eta[n["id"]] for n in sv) / wp / 60, 1),
        "total_travel_min": round(sum(r["total_s"] for r in routes) / 60, 1),
    }
    return {"routes": routes, "metrics": metrics}


def make_orders(depots, vehicles, needs, routes, tab, plan_id):
    nmap = {n["id"]: n for n in needs}
    vmap = {v["id"]: v for v in vehicles}
    need_by = {d: {} for d in depots}
    for r in routes:
        d = vmap[r["vehicle_id"]]["depot_id"]
        for s in r["stops"]:
            n = nmap[s["need_id"]]
            for t in n["types"]:
                need_by[d][t] = need_by[d].get(t, 0) + n["people"] * KG.get(t, 1)
    orders, k = [], 1
    for d, items in need_by.items():
        for t, qty in items.items():
            short = qty - depots[d]["stock"].get(t, 0)
            if short <= 0:
                continue
            for o, od in depots.items():
                if o == d:
                    continue
                spare = od["stock"].get(t, 0) - need_by[o].get(t, 0)
                if spare > 0 and depots[o]["node"] in tab.get(depots[d]["node"], ({},))[0]:
                    mv = min(short, spare)
                    short -= mv
                    orders.append(
                        {
                            "id": f"TO-{plan_id}-{k}",
                            "kind": "Stock transfer",
                            "item": t,
                            "qty_kg": round(mv),
                            "from": od["name"],
                            "to": depots[d]["name"],
                            "reason": f"{depots[d]['name']} short of {t} for assigned needs",
                        }
                    )
                    k += 1
            if short > 0:
                orders.append(
                    {
                        "id": f"PR-{plan_id}-{k}",
                        "kind": "Procurement request",
                        "item": t,
                        "qty_kg": round(short),
                        "from": "District supply office",
                        "to": depots[d]["name"],
                        "reason": "No depot with spare stock reachable by road",
                    }
                )
                k += 1
    return orders
