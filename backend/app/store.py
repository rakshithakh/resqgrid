"""Database access, report ingestion (extract, locate, merge, trust, priority) and dispatch planning."""

from __future__ import annotations
import json
import math
import os
import random
import sqlite3
import threading
import time
from . import core
from .extract import extract

DB = os.getenv("RESQ_DB", "resqgrid.db")
lock = threading.RLock()
_c = None
MAP = core.init()
G = MAP["G"]
DEPOTS = {
    k: {**v, "pos": core.coords(G, v["node"]), "stock": dict(v["stock"])} for k, v in MAP["depots"].items()
}
VEHICLES = core.VEHICLES
STATE = {"plan": None, "dirty": True, "version": 0, "plan_seq": 0, "dirty_at": 0.0}


def db():
    global _c
    if _c is None:
        _c = sqlite3.connect(DB, check_same_thread=False)
        _c.row_factory = sqlite3.Row
        _c.executescript("""
        create table if not exists reports(id integer primary key autoincrement, ticket text unique, phone text, name text,
          text text, lang text, received_at real, extracted text, confidence real, rate_flag integer default 0, need_id integer);
        create table if not exists needs(id integer primary key autoincrement, node text, label text, types text, people integer,
          vulnerable text, flags text default '[]', trust real, confidence real, status text, locked integer default 0,
          first_at real, last_at real, summary text);
        create table if not exists hazards(id integer primary key autoincrement, lat real, lng real, radius real, kind text,
          label text, created_at real);
        create table if not exists events(id integer primary key autoincrement, ts real, level text, msg text);
        create table if not exists plans(id integer primary key autoincrement, created_at real, trigger text, payload text);
        """)
        for col in (
            "verified integer default 1",
            "lat real",
            "lng real",
            "gps_state integer default 0",
            "source text default 'web'",
            "acc real",
        ):
            try:
                _c.execute("alter table reports add column " + col)
                _c.commit()
            except sqlite3.OperationalError:
                pass
    return _c


def query(sql, a=()):
    with lock:
        return [dict(r) for r in db().execute(sql, a).fetchall()]


def execute(sql, a=()):
    with lock:
        cur = db().execute(sql, a)
        db().commit()
        return cur.lastrowid


def log(msg, level="info"):
    execute("insert into events(ts,level,msg) values(?,?,?)", (time.time(), level, msg))


def touch():
    STATE["dirty"] = True
    STATE["dirty_at"] = time.time()
    STATE["version"] += 1


def node_from_text(s):
    return core.parse_node(s) if s else None


def need_view(r, now=None):
    now = now or time.time()
    types = json.loads(r["types"]) or ["other"]
    vul = json.loads(r["vulnerable"])
    node = node_from_text(r["node"])
    people = r["people"]
    raw = (
        min(people, 300)
        * (1 + min(1.0, 0.35 * len(vul)))
        * max(core.TYPEW[t] for t in types)
        * (1 + 0.3 * min(4.0, max(0, (now - r["first_at"]) / 3600)))
        * (0.5 + 0.5 * r["trust"])
    )
    ll = core.coords(G, node) if node else None
    return {
        "id": r["id"],
        "node": node,
        "pos": ll,
        "lat": ll[0] if ll else None,
        "lng": ll[1] if ll else None,
        "label": r["label"],
        "types": types,
        "people": people,
        "vulnerable": vul,
        "flags": json.loads(r["flags"]),
        "trust": round(r["trust"], 2),
        "confidence": round(r["confidence"], 2),
        "status": r["status"],
        "locked": bool(r["locked"]),
        "first_at": r["first_at"],
        "summary": r["summary"],
        "priority": round(100 * (1 - math.exp(-raw / 150))),
        "reports": r.get("nreports", 1),
        "gps": r.get("ngps", 0) > 0,
        "gps_at": (
            {"lat": r["glat"], "lng": r["glng"], "acc": r["gacc"]} if r.get("glat") is not None else None
        ),
        "sms": r.get("nsms", 0) > 0,
        "demand_kg": min(450, max(10, round(sum(people * core.KG[t] for t in types)))) if people else 10,
    }


def needs_view(statuses=None):
    rows = query(
        "select n.*, (select count(*) from reports where need_id=n.id) nreports, (select count(*) from reports where need_id=n.id and gps_state=1) ngps, (select count(*) from reports where need_id=n.id and source='sms') nsms, (select lat from reports where need_id=n.id and lat is not null order by received_at desc limit 1) glat, (select lng from reports where need_id=n.id and lat is not null order by received_at desc limit 1) glng, (select acc from reports where need_id=n.id and lat is not null order by received_at desc limit 1) gacc from needs n order by n.id"
    )
    now = time.time()
    out = [need_view(r, now) for r in rows]
    return [n for n in out if not statuses or n["status"] in statuses]


def hazards():
    return query("select * from hazards order by id")


def recalc(nid):
    n = query("select * from needs where id=?", (nid,))[0]
    reps = query("select * from reports where need_id=?", (nid,))
    ex = [json.loads(r["extracted"]) for r in reps]
    types = []
    [types.append(t) for e in ex for t in e["need_types"] if t not in types]
    types = [t for t in types if t != "other"] or ["other"]
    people = max(e["people"] for e in ex)
    vul = sorted({v for e in ex for v in e["vulnerable"]})
    phones = len({r["phone"] for r in reps if r["verified"]})
    conf = sum(r["confidence"] for r in reps) / len(reps)
    node = node_from_text(n["node"])
    flags = []
    trust = 0.55
    if node is None:
        trust -= 0.3
        flags.append("Location could not be matched to a ward or landmark")
    else:
        trust += 0.1
        near = [h for h in hazards() if core.hav((h["lat"], h["lng"]), core.coords(G, node)) < 700]
        if "rescue" in types and MAP["highground"](node) and not near:
            trust -= 0.4
            flags.append(
                "Reports stranding by water, but location is on high ground with no recorded flood hazard"
            )
    if phones > 1:
        trust += min(0.3, 0.15 * (phones - 1))
        flags.append(f"Corroborated by {phones} independent reporters")
    if people > 800:
        trust -= 0.3
        flags.append(f"Implausible head-count ({people})")
    if any(r["rate_flag"] for r in reps):
        trust -= 0.3
        flags.append("Reporter exceeded rate limit")
    gs = [r["gps_state"] or 0 for r in reps]
    if any(g == 1 for g in gs):
        trust += 0.1
        flags.append("Location confirmed by phone GPS")
    elif any(g == -1 for g in gs):
        trust -= 0.3
        flags.append("Phone GPS is far from the location given in the message")
    if any(r["verified"] for r in reps):
        trust += 0.05
    else:
        trust -= 0.25
        flags.append("Mobile number not verified by one-time code")
    if conf < 0.55:
        flags.append("Low extraction confidence")
    if types == ["other"]:
        flags.append("Need type not recognised. Officer should read the message")
    trust = max(0.05, min(1.0, trust))
    status = n["status"]
    if n["locked"]:
        trust = max(trust, 0.9) if status == "verified" else trust
    elif status in ("verified", "review"):
        status = "verified" if (trust >= 0.5 and conf >= 0.55 and node and types != ["other"]) else "review"
    execute(
        "update needs set types=?,people=?,vulnerable=?,flags=?,trust=?,confidence=?,status=?,last_at=? where id=?",
        (
            json.dumps(types),
            people,
            json.dumps(vul),
            json.dumps(flags),
            trust,
            conf,
            status,
            time.time(),
            nid,
        ),
    )


def ingest(
    text,
    phone="",
    name="",
    hint_place=None,
    received_at=None,
    quiet=False,
    verified=True,
    gps=None,
    source="web",
):
    now = received_at or time.time()
    ext = extract(text)
    place = core.match_place(text) or (core.match_place(hint_place) if hint_place else None)
    ext.confidence = min(1.0, ext.confidence + (0.2 if place else 0))
    rate = (
        len(query("select id from reports where phone=? and received_at>?", (phone, now - 600))) >= 3
        if phone
        else False
    )
    ticket = f"RG-{random.randint(100000, 999999)}"
    node = place[1] if place else None
    label = place[0] if place else "Unknown location"
    gstate, glat, glng, gacc = 0, None, None, None
    if gps:
        glat, glng = gps[0], gps[1]
        gacc = gps[2] if len(gps) > 2 else None
        gn, gd = core.snap(glat, glng)
        if gd > MAP["service_m"]:
            gstate = -1  # GPS is outside the service area
        elif node is None:
            node, gstate = gn, 1
            label = core.nearest_label(gn)  # no place in text: GPS gives the location
        else:
            gstate = 1 if core.hav(core.coords(G, node), core.coords(G, gn)) <= 1500 else -1
    nid = None
    if node and verified and ext.need_types != ["other"]:
        for n in query(
            "select * from needs where node=? and status in ('verified','review') and first_at>?",
            (core.node_key(node), now - 10800),
        ):
            if set(json.loads(n["types"])) & set(ext.need_types):
                nid = n["id"]
                break
    if nid is None:
        nid = execute(
            "insert into needs(node,label,types,people,vulnerable,trust,confidence,status,first_at,last_at,summary) values(?,?,?,?,?,?,?,?,?,?,?)",
            (
                core.node_key(node) if node else None,
                label,
                "[]",
                0,
                "[]",
                0.5,
                0.5,
                "verified",
                now,
                now,
                text[:200],
            ),
        )
    execute(
        "insert into reports(ticket,phone,name,text,lang,received_at,extracted,confidence,rate_flag,need_id,verified,lat,lng,gps_state,source,acc) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            ticket,
            phone,
            name,
            text,
            ext.language,
            now,
            ext.model_dump_json(),
            ext.confidence,
            int(rate),
            nid,
            int(verified),
            glat,
            glng,
            gstate,
            source,
            gacc,
        ),
    )
    recalc(nid)
    touch()
    nv = [n for n in needs_view() if n["id"] == nid][0]
    if not quiet:
        log(
            f"Report {ticket} ({ext.language}, {ext.source}) -> {nv['label']}: {', '.join(nv['types'])}, {nv['people']} people. Status: {nv['status']}"
        )
        if nv["status"] == "review":
            log(f"Report {ticket} sent to review queue: {'; '.join(nv['flags']) or 'low confidence'}", "warn")
    return {
        "gps": gstate,
        "ticket": ticket,
        "need_id": nid,
        "status": nv["status"],
        "label": nv["label"],
        "types": nv["types"],
        "people": nv["people"],
        "language": ext.language,
        "extraction_source": ext.source,
    }


def solve_plan(trigger="manual"):
    with lock:
        needs = [n for n in needs_view({"verified"}) if n["node"]]
        if not needs:  # nothing to plan: no empty plan on screen
            STATE["plan"] = None
            STATE["dirty"] = False
            STATE["version"] += 1
            return None
        hz = hazards()
        mult = core.edge_mult(G, hz)
        tab = core.tables(G, mult, [d["node"] for d in DEPOTS.values()] + [n["node"] for n in needs])
        a_opt, engine = core.optimized_assign(tab, VEHICLES, DEPOTS, needs)
        opt = core.evaluate(G, tab, VEHICLES, DEPOTS, needs, a_opt)
        base = core.evaluate(G, tab, VEHICLES, DEPOTS, needs, core.baseline_assign(VEHICLES, DEPOTS, needs))
        STATE["plan_seq"] += 1
        pid = STATE["plan_seq"]
        orders = core.make_orders(DEPOTS, VEHICLES, needs, opt["routes"], tab, pid)
        mo, mb = opt["metrics"], base["metrics"]
        blocked = sum(1 for v in mult.values() if v == math.inf)
        summary = (
            f"Plan #{pid}: {mo['needs_served']} of {mo['needs_total']} verified needs covered ({mo['people_reached']} people) "
            f"with {len(opt['routes'])} vehicles, avoiding {blocked} closed road segment(s). "
            f"Priority-weighted arrival {mo['weighted_eta_min']} min vs {mb['weighted_eta_min']} min for first-come nearest-truck dispatch. "
            f"{len(orders)} stock order(s) raised."
        )
        plan = {
            "id": pid,
            "created_at": time.time(),
            "trigger": trigger,
            "engine": engine,
            "approved": False,
            "approved_at": None,
            "optimized": opt,
            "baseline": base,
            "orders": orders,
            "summary": summary,
            "blocked_segments": blocked,
        }
        STATE["plan"] = plan
        STATE["dirty"] = False
        STATE["version"] += 1
        execute(
            "insert into plans(created_at,trigger,payload) values(?,?,?)",
            (time.time(), trigger, json.dumps(plan)),
        )
        log(f"Agent: {summary}")
        return plan


def approve():
    p = STATE["plan"]
    if p and not p["approved"]:
        p["approved"] = True
        p["approved_at"] = time.time()
        STATE["version"] += 1
        log(f"Dispatch approved for plan #{p['id']}: {len(p['optimized']['routes'])} vehicles released")
    return p


SCENARIO = [
    ("Ward 7 mein 40 log chhat par fase hain, paani aur dawai chahiye. Bachche bhi hain", "9845010001", 55),
    ("ward 7 near river 12 families stuck, need boat and drinking water urgent", "9845010002", 40),
    ("Ward 4 - 25 people stranded, 3 elderly, need food and medicine", "9845010003", 35),
    ("वार्ड 10 में 18 लोग फंसे हैं, पानी और खाना चाहिए", "9845010004", 30),
    (
        "Old Bridge Road side 60 people need shelter and blankets, children and pregnant women",
        "9845010005",
        28,
    ),
    ("ವಾರ್ಡ್ 9 ನಲ್ಲಿ 30 ಜನ ಆಹಾರ ಮತ್ತು ನೀರು ಬೇಕು", "9845010006", 25),
    ("Ward 11: 15 people need drinking water, no electricity since morning", "9845010007", 22),
    ("Market Yard godown flooded, 8 workers trapped on first floor, one injured", "9845010008", 20),
    ("Ward 2 insulin required for 2 patients, bedridden elderly", "9845010009", 18),
    ("Ward 8 around 50 people need food packets", "9845010010", 15),
    ("Govt High School relief camp has 120 people, need water and food and blankets", "9845010011", 12),
    ("Ward 12 5 people need water", "9845010012", 10),
    ("Ward 3 20 log fase hain chhat par bachao bachao", "9845099999", 5),
    ("Ward 1 5000 people need rescue boat urgent", "9000000001", 4),
    ("Ward 7 mein 35 log fase hai chhat par, paani chahiye", "9845010013", 8),
    ("help help flood in our area send people", "9845010014", 3),
    ("Civil Hospital 30 patients need medicine and drinking water", "9845010015", 6),
]


def reset_scenario():
    with lock:
        for t in ("reports", "needs", "hazards", "events", "plans"):
            execute(f"delete from {t}")
        now = time.time()

        def at(w):
            return core.coords(G, MAP["wards"][MAP["ward_nums"][w]])

        gps = {
            0: at(7),
            2: at(4),
            3: at(10),
            12: at(10),
        }  # index 12 is the fake Ward 3 report: GPS is far away
        sms = {8, 11}
        for i, (text, phone, mins) in enumerate(SCENARIO):
            ingest(
                text,
                phone,
                "Demo",
                received_at=now - mins * 60,
                quiet=True,
                verified=phone not in ("9845099999", "9000000001"),
                gps=gps.get(i),
                source="sms" if i in sms else "web",
            )
        log(f"Scenario loaded: {len(SCENARIO)} reports ingested through the live pipeline")
        for n in needs_view({"review"}):
            log(f"Need #{n['id']} ({n['label']}) held for human review: {'; '.join(n['flags'])}", "warn")
        STATE["plan"] = None
        touch()


def check_map():
    """If the map changed (e.g. demo grid -> real OSM), old needs point at nodes that no longer exist. Clear them."""
    rows = query("select node from needs where node is not null")
    if any(core.parse_node(r["node"]) not in G for r in rows):
        for t in ("reports", "needs", "hazards", "events", "plans"):
            execute(f"delete from {t}")
        log("Map changed: old demo data cleared", "warn")


def clear_all(who="officer"):
    with lock:
        for t in ("reports", "needs", "hazards", "events", "plans"):
            execute(f"delete from {t}")
        STATE["plan"] = None
        STATE["dirty"] = False
        STATE["version"] += 1
        log(f"All data cleared by {who}", "warn")
