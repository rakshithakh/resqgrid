from __future__ import annotations
import asyncio
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import urllib.parse
from fastapi import Depends, FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from . import core, evalset, smsout, store
from .store import STATE, execute, query

SECRET = os.getenv("RESQ_SECRET", "dev-secret-change-me").encode()
if SECRET == b"dev-secret-change-me" and os.getenv("PORT"):
    print("[security] WARNING: set RESQ_SECRET to a long random value on your host")
USERS = {
    "controlroom": ("Relief@2026", "Duty Officer, Control Room"),
    "collector": ("Collector@2026", "District Relief Coordinator"),
}
app = FastAPI(title="ResQGrid API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
sockets: set[WebSocket] = set()
GEO = core.map_geometry()
SMS_SECRET = os.getenv("SMS_SECRET", "demo-sms-secret")
DRIVER_PIN = os.getenv("DRIVER_PIN", "1234")
LIVE: dict = {}


def make_token(payload, ttl):
    body = base64.urlsafe_b64encode(json.dumps({**payload, "exp": time.time() + ttl}).encode()).decode()
    return body + "." + hmac.new(SECRET, body.encode(), hashlib.sha256).hexdigest()


def read_token(tok):
    body, sig = tok.split(".")
    if not hmac.compare_digest(sig, hmac.new(SECRET, body.encode(), hashlib.sha256).hexdigest()):
        raise ValueError("bad signature")
    d = json.loads(base64.urlsafe_b64decode(body))
    if d["exp"] < time.time():
        raise ValueError("expired")
    return d


def officer(authorization: str = Header(default="")):
    try:
        d = read_token(authorization.removeprefix("Bearer "))
        return {"username": d["u"], "title": USERS[d["u"]][1]}
    except Exception:
        raise HTTPException(401, "Session expired or invalid. Please sign in again.") from None


PHONE_RE = re.compile(r"^[6-9]\d{9}$")
DEMO_OTP = (
    os.getenv("DEMO_OTP", "1") == "1"
)  # shows the code on screen; set 0 once a real SMS gateway is wired in
OTP: dict = {}
FAILS: dict = {}
IPS: dict = {}
print(f"[sms] provider={smsout.provider()} demo_code_on_screen={DEMO_OTP}")


class Login(BaseModel):
    username: str
    password: str


class ReportIn(BaseModel):
    text: str = Field(min_length=5, max_length=1000)
    phone: str = Field(default="", max_length=15)
    name: str = Field(default="", max_length=60)
    ward: str = Field(default="", max_length=40)
    token: str = ""
    unverified: bool = False
    acc: float | None = Field(default=None, ge=0, le=100000)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)


class OtpReq(BaseModel):
    phone: str


class SmsDemo(BaseModel):
    sender: str
    text: str = Field(max_length=480)


class DriverLogin(BaseModel):
    vehicle_id: str
    pin: str


class Loc(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    acc: float | None = None


class OtpVerify(BaseModel):
    phone: str
    code: str


class HazardIn(BaseModel):
    lat: float
    lng: float
    radius: float = Field(default=350, ge=100, le=1500)
    kind: str = Field(default="blocked", pattern="^(blocked|slow)$")
    label: str = Field(default="Flooded road", max_length=60)


class LocateIn(BaseModel):
    place: str


@app.post("/api/auth/login")
def login(b: Login):
    k = b.username.strip().lower()
    f = FAILS.get(k, [0, 0.0])
    if f[1] > time.time():
        raise HTTPException(
            429, f"Too many failed attempts. Try again in {int((f[1] - time.time()) / 60) + 1} minute(s)."
        )
    u = USERS.get(k)
    if not u or not hmac.compare_digest(u[0], b.password):
        f[0] += 1
        if f[0] >= 5:
            f = [0, time.time() + 300]
        FAILS[k] = f
        raise HTTPException(401, "Invalid user ID or password.")
    FAILS.pop(k, None)
    return {"token": make_token({"u": k}, 8 * 3600), "user": {"username": k, "title": u[1]}}


@app.get("/api/auth/me")
def me(o=Depends(officer)):
    return o


@app.get("/api/config")
def config():
    return {
        "mode": core.MAP["mode"],
        "tiles": core.MAP["tiles"],
        "center": list(core.MAP["center"]),
        "demo": DEMO_OTP,
        "places": [p["name"] for p in GEO["places"]],
        "gemini": bool(os.getenv("GEMINI_API_KEY")),
        "vehicles": [{"id": v["id"], "name": v["name"]} for v in store.VEHICLES],
    }


@app.get("/api/public/status")
def public_status():
    needs = store.needs_view()
    open_ = [n for n in needs if n["status"] in ("verified", "review")]
    by = {}
    for n in open_:
        for t in n["types"]:
            by[t] = by.get(t, 0) + 1
    plan = STATE["plan"]
    return {
        "reports": query("select count(*) c from reports")[0]["c"],
        "open_needs": len(open_),
        "people_affected": sum(n["people"] for n in open_ if n["status"] == "verified"),
        "vehicles": len(store.VEHICLES),
        "depots": len(store.DEPOTS),
        "by_type": by,
        "hazards": [{"label": h["label"], "kind": h["kind"]} for h in store.hazards()],
        "plan_approved": bool(plan and plan["approved"]),
        "wards": sorted(
            [
                {"label": n["label"], "types": n["types"], "people": n["people"], "status": n["status"]}
                for n in open_
                if n["status"] == "verified"
            ],
            key=lambda w: -w["people"],
        )[:8],
    }


@app.post("/api/public/otp/request")
def otp_request(b: OtpReq, request: Request):
    p = b.phone.strip()
    if not PHONE_RE.match(p):
        raise HTTPException(422, "Enter a valid 10-digit Indian mobile number.")
    if smsout.provider() != "demo":  # real SMS costs money: cap per client address too
        ip = request.client.host if request.client else "?"
        now_ = time.time()
        IPS[ip] = [t for t in IPS.get(ip, []) if t > now_ - 3600]
        if len(IPS[ip]) >= 8:
            raise HTTPException(429, "Too many codes requested from this connection. Try again later.")
        IPS[ip].append(now_)
    now = time.time()
    o = OTP.get(p, {"sent": []})
    o["sent"] = [t for t in o["sent"] if t > now - 600]
    if len(o["sent"]) >= 3:
        raise HTTPException(429, "Too many codes requested. Try again in a few minutes.")
    code = f"{secrets.randbelow(10**6):06d}"
    o.update(code=code, exp=now + 300, tries=0)
    o["sent"].append(now)
    OTP[p] = o
    if smsout.provider() == "demo":
        print(f"[SMS-DEMO] OTP for {p}: {code}")
    else:
        try:
            smsout.send_otp(p, code)
        except RuntimeError as e:
            OTP.pop(p, None)
            print(f"[sms] FAILED to send code to {p}: {e}")
            raise HTTPException(
                502,
                "We could not send the SMS right now. Try again in a minute, or send an SMS request instead.",
            ) from None
    r = {"sent": True, "expires_in": 300, "channel": "sms" if smsout.provider() != "demo" else "demo"}
    if DEMO_OTP and smsout.provider() == "demo":
        r["demo_code"] = code  # never show the code on screen when real SMS is on
    return r


@app.post("/api/public/otp/verify")
def otp_verify(b: OtpVerify):
    p = b.phone.strip()
    o = OTP.get(p)
    if not o or not o.get("code") or o["exp"] < time.time():
        raise HTTPException(400, "Code expired. Request a new one.")
    o["tries"] += 1
    if o["tries"] > 5:
        o["code"] = None
        raise HTTPException(429, "Too many wrong attempts. Request a new code.")
    if not hmac.compare_digest(o["code"], b.code.strip()):
        raise HTTPException(400, "Incorrect code.")
    o["code"] = None
    return {"token": make_token({"p": p}, 7 * 86400), "phone": p, "days": 7}


@app.post("/api/public/report")
async def submit(b: ReportIn):
    phone = b.phone.strip()
    if not PHONE_RE.match(phone):
        raise HTTPException(422, "Enter a valid 10-digit Indian mobile number.")
    verified = False
    if b.token:
        try:
            verified = read_token(b.token).get("p") == phone
        except Exception:
            verified = False
        if not verified:
            raise HTTPException(401, "Verification expired. Please verify your mobile number again.")
    elif not b.unverified:
        raise HTTPException(
            403, "Verify your mobile number first, or send as an unverified emergency request."
        )
    gps = (b.lat, b.lng, b.acc) if b.lat is not None and b.lng is not None else None
    r = store.ingest(b.text, phone, b.name.strip(), b.ward or None, verified=verified, gps=gps, source="web")
    r["verified"] = verified
    await broadcast()
    return r


def _status_for(r, nmap):
    n = nmap[r["need_id"]]
    eta = veh = None
    plan = STATE["plan"]
    if plan and plan["approved"]:
        for rt in plan["optimized"]["routes"]:
            for st in rt["stops"]:
                if st["need_id"] == n["id"]:
                    eta, veh = round(st["eta_s"] / 60), rt["vehicle_id"]
    text = {
        "verified": "Verified. Included in the relief dispatch queue.",
        "review": "Under verification by the control room.",
        "rejected": "Could not be verified. Please call the helpline.",
    }.get(n["status"], n["status"])
    if eta is not None:
        text = f"Relief vehicle {veh} dispatched. Estimated arrival in about {eta} minutes (simulated)."
    return {
        "ticket": r["ticket"],
        "received_at": r["received_at"],
        "location": n["label"],
        "needs": n["types"],
        "status": n["status"],
        "message": text,
        "eta_min": eta,
        "source": r.get("source") or "web",
    }


@app.get("/api/public/track/{ticket}")
def track(ticket: str):
    r = query("select * from reports where ticket=?", (ticket.strip().upper(),))
    if not r:
        raise HTTPException(404, "No request found for this reference number.")
    return _status_for(r[0], {n["id"]: n for n in store.needs_view()})


def citizen(authorization: str = Header(default="")):
    try:
        return read_token(authorization.removeprefix("Bearer "))["p"]
    except Exception:
        raise HTTPException(401, "Please sign in with your mobile number.") from None


@app.get("/api/me/requests")
def my_requests(phone: str = Depends(citizen)):
    nmap = {n["id"]: n for n in store.needs_view()}
    return {
        "phone": phone,
        "requests": [
            {**_status_for(r, nmap), "text": r["text"]}
            for r in query("select * from reports where phone=? order by received_at desc limit 25", (phone,))
        ],
    }


def _sms(sender: str, text: str):
    phone = re.sub(r"\D", "", sender)[-10:]
    if not PHONE_RE.match(phone):
        raise HTTPException(422, "Invalid sender number")
    t = text.strip()
    if not t:
        raise HTTPException(422, "Empty message")
    up = t.upper()
    if up in ("HELP", "INFO", "?"):
        return {
            "reply": "ResQGrid relief: text what you need, how many people and where. Example: WARD 7 40 PEOPLE NEED WATER. Text STATUS to check your last request. Emergency: call 112.",
            "ticket": None,
        }
    if up.startswith("STATUS"):
        parts = up.split()
        rows = (
            query("select * from reports where ticket=?", (parts[1],))
            if len(parts) > 1
            else query("select * from reports where phone=? order by received_at desc limit 1", (phone,))
        )
        if not rows or rows[0]["phone"] != phone:
            return {
                "reply": "No request found for this number. Text your need to create one.",
                "ticket": None,
            }
        i = _status_for(rows[0], {n["id"]: n for n in store.needs_view()})
        return {"reply": f"ResQGrid {i['ticket']}: {i['message']}", "ticket": i["ticket"]}
    r = store.ingest(t, phone, "", None, verified=True, source="sms")
    need = ", ".join(r["types"])
    ppl = f"{r['people']} people" if r["people"] else "number of people not stated"
    state = (
        "Verified, in dispatch queue." if r["status"] == "verified" else "Under review by the control room."
    )
    return {
        "reply": f"ResQGrid: request {r['ticket']} received for {r['label']}: {need}, {ppl}. {state} Text STATUS to check. Emergency: call 112.",
        "ticket": r["ticket"],
        "status": r["status"],
    }


@app.post("/api/sms/inbound")
async def sms_inbound(request: Request, x_sms_secret: str = Header(default=""), key: str = ""):
    """Inbound SMS webhook. Takes the Android SMS Gateway sms:received event or plain JSON/form fields.
    The shared secret goes in X-SMS-Secret, or in ?key= for gateways that cannot set headers."""
    if not hmac.compare_digest(x_sms_secret or key, SMS_SECRET):
        raise HTTPException(401, "Bad gateway secret")
    raw = await request.body()
    try:
        d = json.loads(raw)
    except Exception:
        d = {k: v[0] for k, v in urllib.parse.parse_qs(raw.decode()).items()}
    if d.get("event") and isinstance(d.get("payload"), dict):  # Android SMS Gateway webhook format
        if d["event"] != "sms:received":
            return {"ignored": d["event"]}
        sender, text = d["payload"].get("phoneNumber", ""), d["payload"].get("message", "")
    else:
        sender, text = (
            d.get("from") or d.get("From") or d.get("sender") or "",
            d.get("text") or d.get("Body") or d.get("message") or "",
        )
    r = _sms(sender, text)
    if smsout.provider() == "android" and r.get("reply"):  # answer the sender from the same phone
        try:
            await asyncio.to_thread(smsout.send_text, re.sub(r"\D", "", sender)[-10:], r["reply"])
        except RuntimeError as e:
            print(f"[sms] reply not sent: {e}")
    await broadcast()
    return r


@app.post("/api/public/sms-demo")
async def sms_demo(b: SmsDemo):
    """Phone simulator for the demo. The sender is typed by the user, so it only exists when DEMO_OTP=1."""
    if not DEMO_OTP:
        raise HTTPException(404, "Not found")
    r = _sms(b.sender, b.text)
    await broadcast()
    return r


def driver(authorization: str = Header(default="")):
    try:
        v = read_token(authorization.removeprefix("Bearer "))["v"]
        if v not in {x["id"] for x in store.VEHICLES}:
            raise ValueError
        return v
    except Exception:
        raise HTTPException(401, "Driver session expired. Sign in again.") from None


@app.post("/api/driver/login")
def driver_login(b: DriverLogin):
    if b.vehicle_id not in {x["id"] for x in store.VEHICLES} or not hmac.compare_digest(b.pin, DRIVER_PIN):
        raise HTTPException(401, "Wrong vehicle or PIN.")
    return {"token": make_token({"v": b.vehicle_id}, 12 * 3600), "vehicle_id": b.vehicle_id}


@app.post("/api/driver/location")
async def driver_loc(b: Loc, v: str = Depends(driver)):
    LIVE[v] = {"lat": b.lat, "lng": b.lng, "acc": b.acc, "ts": time.time()}
    await broadcast()
    return {"ok": True}


@app.get("/api/driver/route")
def driver_route(v: str = Depends(driver)):
    plan = STATE["plan"]
    for r in plan["optimized"]["routes"] if plan else []:
        if r["vehicle_id"] == v:
            return {"route": r, "approved": plan["approved"]}
    return {"route": None, "approved": bool(plan and plan["approved"])}


@app.get("/api/map")
def map_(o=Depends(officer)):
    return {
        **GEO,
        "depots": [
            {"id": d["id"], "name": d["name"], "lat": d["pos"][0], "lng": d["pos"][1], "stock": d["stock"]}
            for d in store.DEPOTS.values()
        ],
        "vehicles": store.VEHICLES,
        "center": core.CENTER,
    }


@app.get("/api/state")
def state(o=Depends(officer)):
    plan = STATE["plan"]
    needs = store.needs_view()
    for n in needs:
        n.pop("node")
        n.pop("pos")
    return {
        "version": STATE["version"],
        "server_time": time.time(),
        "needs": needs,
        "hazards": store.hazards(),
        "plan": plan,
        "stale": STATE["dirty"],
        "events": query("select * from events order by id desc limit 40"),
        "approval_elapsed_s": (time.time() - plan["approved_at"]) if plan and plan["approved"] else None,
        "live": {
            k: {"lat": v["lat"], "lng": v["lng"], "age_s": round(time.time() - v["ts"])}
            for k, v in LIVE.items()
            if time.time() - v["ts"] < 90
        },
    }


@app.post("/api/hazards")
async def add_hazard(h: HazardIn, o=Depends(officer)):
    i = execute(
        "insert into hazards(lat,lng,radius,kind,label,created_at) values(?,?,?,?,?,?)",
        (h.lat, h.lng, h.radius, h.kind, h.label, time.time()),
    )
    store.log(f"{o['title']} marked hazard #{i}: {h.label} ({h.kind}, {int(h.radius)} m)", "warn")
    for n in store.query("select id from needs where status in ('verified','review') and locked=0"):
        store.recalc(n["id"])
    store.touch()
    await broadcast()
    return {"id": i}


@app.delete("/api/hazards/{hid}")
async def del_hazard(hid: int, o=Depends(officer)):
    execute("delete from hazards where id=?", (hid,))
    store.log(f"Hazard #{hid} cleared by {o['title']}")
    store.touch()
    await broadcast()
    return {"ok": True}


@app.post("/api/needs/{nid}/{action}")
async def need_action(nid: int, action: str, b: LocateIn | None = None, o=Depends(officer)):
    if not query("select id from needs where id=?", (nid,)):
        raise HTTPException(404, "Need not found")
    if action == "verify":
        execute("update needs set status='verified',locked=1 where id=?", (nid,))
    elif action == "reject":
        execute("update needs set status='rejected',locked=1 where id=?", (nid,))
    elif action == "locate":
        m = core.match_place(b.place if b else "")
        if not m:
            raise HTTPException(422, "Place not recognised. Use a ward number (e.g. Ward 5) or a landmark.")
        execute("update needs set node=?,label=? where id=?", (core.node_key(m[1]), m[0], nid))
    else:
        raise HTTPException(400, "Unknown action")
    if action != "reject":
        store.recalc(nid)
    store.log(f"Need #{nid}: {action} by {o['title']}")
    store.touch()
    await broadcast()
    return {"ok": True}


@app.post("/api/plan/solve")
async def solve(o=Depends(officer)):
    p = await asyncio.to_thread(store.solve_plan, f"manual ({o['username']})")
    await broadcast()
    if not p:
        raise HTTPException(409, "No verified needs to plan yet.")
    return {"id": p["id"]}


@app.post("/api/plan/approve")
async def approve(o=Depends(officer)):
    if not STATE["plan"]:
        raise HTTPException(409, "No plan to approve")
    if STATE["dirty"]:
        raise HTTPException(409, "Plan is out of date. Wait for the replan to finish.")
    store.approve()
    await broadcast()
    return {"ok": True}


@app.post("/api/simulate/scenario")
async def scenario(o=Depends(officer)):
    await asyncio.to_thread(store.reset_scenario)
    await broadcast()
    return {"ok": True}


@app.post("/api/admin/clear")
async def clear_all(o=Depends(officer)):
    """Delete every report, need, hazard, plan and log entry."""
    await asyncio.to_thread(store.clear_all, o["title"])
    LIVE.clear()
    await broadcast()
    return {"ok": True}


@app.get("/api/eval/extraction")
def evaluation(o=Depends(officer)):
    return evalset.run()


async def broadcast():
    for ws in list(sockets):
        try:
            await ws.send_text(json.dumps({"version": STATE["version"]}))
        except Exception:
            sockets.discard(ws)


@app.websocket("/ws")
async def ws(w: WebSocket):
    await w.accept()
    sockets.add(w)
    try:
        while True:
            await w.receive_text()
    except WebSocketDisconnect:
        sockets.discard(w)


async def agent_loop():
    """Watches for new reports and hazard changes, then replans without being asked."""
    while True:
        await asyncio.sleep(1)
        if STATE["dirty"] and time.time() - STATE["dirty_at"] > 1.2:
            store.log("Agent: change detected (new report or hazard). Recomputing dispatch plan")
            try:
                await asyncio.to_thread(store.solve_plan, "agent")
            except Exception as e:
                store.log(f"Agent error: {e}", "error")
                STATE["dirty"] = False
            await broadcast()


@app.on_event("startup")
async def start():
    store.check_map()
    if os.getenv("AUTOSEED", "0") == "1" and not query("select id from reports limit 1"):
        await asyncio.to_thread(store.reset_scenario)
    asyncio.create_task(agent_loop())


DIST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend", "dist"
)
if os.path.isdir(os.path.join(DIST, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def website(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        f = os.path.realpath(os.path.join(DIST, path))
        if path and f.startswith(os.path.realpath(DIST) + os.sep) and os.path.isfile(f):
            return FileResponse(f)
        return FileResponse(os.path.join(DIST, "index.html"))  # single-page app routes (/login, /report, ...)
