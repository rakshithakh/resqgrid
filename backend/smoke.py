import os, time
os.environ["RESQ_DB"]="/tmp/t.db"
if os.path.exists("/tmp/t.db"): os.remove("/tmp/t.db")
from fastapi.testclient import TestClient
from app.main import app
from app import store, evalset
with TestClient(app) as c:
    r=c.post("/api/auth/login",json={"username":"controlroom","password":"Relief@2026"}); assert r.status_code==200,r.text
    h={"Authorization":"Bearer "+r.json()["token"]}
    time.sleep(6)
    s=c.get("/api/state",headers=h).json()
    print("needs",len(s["needs"]),[ (n["id"],n["label"],n["status"],n["priority"],n["trust"]) for n in s["needs"]])
    p=s["plan"]; print("engine",p["engine"]); print(p["summary"])
    print("opt",p["optimized"]["metrics"]); print("base",p["baseline"]["metrics"]); print("orders",p["orders"])
    b=c.get("/api/map",headers=h).json()["bridges"]; print(b)
    for br in b[:2]: c.post("/api/hazards",headers=h,json={"lat":br["lat"],"lng":br["lng"],"radius":350,"kind":"blocked","label":br["label"]+" flooded"})
    time.sleep(6)
    p=c.get("/api/state",headers=h).json()["plan"]; print(p["summary"]); print("opt",p["optimized"]["metrics"]); print("base",p["baseline"]["metrics"])
    print(c.post("/api/plan/approve",headers=h).json())
    t=c.post("/api/public/report",json={"text":"Ward 5 10 log paani chahiye","phone":"9000000009"}).json(); print(t)
    print(c.get("/api/public/track/"+t["ticket"]).json())
    print(c.get("/api/public/status").json()["open_needs"])
    e=c.get("/api/eval/extraction",headers=h).json(); print({k:v for k,v in e.items() if k!="rows"})
    print([r for r in e["rows"] if not (r["types_ok"] and r["people_ok"] and r["location_ok"])])
