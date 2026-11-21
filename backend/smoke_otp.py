import os, time
os.environ["RESQ_DB"]="/tmp/t3.db"
if os.path.exists("/tmp/t3.db"): os.remove("/tmp/t3.db")
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as c:
    P="9812345678"; body={"text":"Ward 5 10 log paani chahiye","phone":P}
    print("no verify ->",c.post("/api/public/report",json=body).status_code)
    print("bad phone ->",c.post("/api/public/otp/request",json={"phone":"12345"}).status_code)
    r=c.post("/api/public/otp/request",json={"phone":P}).json(); print("otp",r)
    print("wrong code ->",c.post("/api/public/otp/verify",json={"phone":P,"code":"000000"}).status_code)
    v=c.post("/api/public/otp/verify",json={"phone":P,"code":r["demo_code"]}).json(); print("verified",v["phone"])
    ok=c.post("/api/public/report",json={**body,"token":v["token"]}).json(); print("verified report ->",ok["status"],ok["verified"])
    print("token for other phone ->",c.post("/api/public/report",json={**body,"phone":"9000000009","token":v["token"]}).status_code)
    un=c.post("/api/public/report",json={"text":"Ward 6 8 log khana chahiye","phone":"9000000008","unverified":True}).json(); print("unverified ->",un["status"],un["verified"])
    for i in range(6): code=c.post("/api/auth/login",json={"username":"controlroom","password":"x"}).status_code
    print("lockout ->",code)
