from app import core, store
from app.extract import rules_extract
from conftest import verified_token

SMS = {"X-SMS-Secret": "demo-sms-secret"}


def test_extracts_romanised_hindi():
    e = rules_extract("Ward 7 mein 40 log chhat par fase hain, paani aur dawai chahiye")
    assert set(e.need_types) == {"rescue", "water", "medical"}
    assert e.people == 40
    assert e.language == "hi-Latn"


def test_extracts_kannada_and_devanagari():
    assert rules_extract("ವಾರ್ಡ್ 9 ನಲ್ಲಿ 30 ಜನ ಆಹಾರ ಮತ್ತು ನೀರು ಬೇಕು").people == 30
    e = rules_extract("वार्ड 10 में 18 लोग फंसे हैं, पानी और खाना चाहिए")
    assert e.people == 18 and "rescue" in e.need_types


def test_disease_words_count_as_medical():
    assert rules_extract("ward 8, 45 people have dengue").need_types == ["medical"]


def test_place_matching():
    assert core.match_place("Ward 7 mein 40 log")[0] == "Ward 7"
    assert core.match_place("near the civil hospital")[0] == "Civil Hospital"
    assert core.match_place("somewhere nobody knows") is None


def test_report_needs_verification_or_emergency_flag(client):
    body = {"text": "Ward 5 12 log paani chahiye", "phone": "9812345678"}
    assert client.post("/api/public/report", json=body).status_code == 403


def test_otp_flow(client):
    phone = "9812345678"
    code = client.post("/api/public/otp/request", json={"phone": phone}).json()["demo_code"]
    wrong = client.post("/api/public/otp/verify", json={"phone": phone, "code": "000000"})
    assert wrong.status_code == 400
    token = client.post("/api/public/otp/verify", json={"phone": phone, "code": code}).json()["token"]
    ok = client.post(
        "/api/public/report", json={"text": "Ward 5 12 log paani chahiye", "phone": phone, "token": token}
    )
    assert ok.json()["verified"] is True
    # a token only works for the number it was issued to
    other = client.post(
        "/api/public/report",
        json={"text": "Ward 5 12 log paani chahiye", "phone": "9000000009", "token": token},
    )
    assert other.status_code == 401


def test_implausible_unverified_report_goes_to_review(client):
    r = client.post(
        "/api/public/report",
        json={
            "text": "Ward 1 5000 people need rescue boat urgent",
            "phone": "9000000001",
            "unverified": True,
        },
    )
    assert r.json()["status"] == "review"


def test_gps_far_from_claimed_place_is_held(client):
    token = verified_token(client, "9812345670")
    lat, lng = core.coords(core.MAP["G"], core.MAP["wards"]["Ward 6"])
    r = client.post(
        "/api/public/report",
        json={
            "text": "Ward 2 30 log fase hain bachao",
            "phone": "9812345670",
            "token": token,
            "lat": lat,
            "lng": lng,
        },
    )
    assert r.json()["status"] == "review"
    assert r.json()["gps"] == -1


def test_sms_needs_secret_and_status_is_private(client):
    msg = {"from": "+919800000001", "text": "Ward 5 12 log paani chahiye"}
    assert client.post("/api/sms/inbound", json=msg).status_code == 401
    reply = client.post("/api/sms/inbound", headers=SMS, json=msg).json()
    assert reply["ticket"].startswith("RG-")
    mine = client.post(
        "/api/sms/inbound", headers=SMS, json={"from": "9800000001", "text": "STATUS " + reply["ticket"]}
    ).json()
    theirs = client.post(
        "/api/sms/inbound", headers=SMS, json={"from": "9800000002", "text": "STATUS " + reply["ticket"]}
    ).json()
    assert reply["ticket"] in mine["reply"]
    assert theirs["ticket"] is None


def test_officer_login_locks_after_five_failures(client):
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "collector", "password": "wrong"})
    locked = client.post("/api/auth/login", json={"username": "collector", "password": "Collector@2026"})
    assert locked.status_code == 429


def test_officer_pages_need_a_token(client):
    assert client.get("/api/state").status_code == 401


def test_plan_covers_needs_and_reroutes_around_a_closed_bridge(client, officer):
    for text, phone in [
        ("Ward 5 12 log paani chahiye", "9800000011"),
        ("Ward 10 20 log khana chahiye", "9800000012"),
        ("Ward 4 8 log dawai chahiye", "9800000013"),
    ]:
        client.post("/api/sms/inbound", headers=SMS, json={"from": phone, "text": text})
    plan = store.solve_plan("test")
    assert plan["optimized"]["metrics"]["needs_served"] == 3

    bridge = client.get("/api/map", headers=officer).json()["bridges"][0]
    client.post(
        "/api/hazards",
        headers=officer,
        json={"lat": bridge["lat"], "lng": bridge["lng"], "radius": 350, "kind": "blocked", "label": "test"},
    )
    plan = store.solve_plan("test")
    assert plan["blocked_segments"] > 0
    assert plan["optimized"]["metrics"]["needs_served"] >= 2


def test_nothing_to_plan_returns_409(client, officer):
    assert client.post("/api/plan/solve", headers=officer).status_code == 409


def test_driver_location_shows_up_for_officers(client, officer):
    token = client.post("/api/driver/login", json={"vehicle_id": "W-01", "pin": "1234"}).json()["token"]
    client.post(
        "/api/driver/location",
        headers={"Authorization": "Bearer " + token},
        json={"lat": 15.36, "lng": 75.12, "acc": 8},
    )
    assert "W-01" in client.get("/api/state", headers=officer).json()["live"]
