import os
import tempfile

# Must be set before the app is imported: it reads these once at startup.
os.environ["RESQ_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["AUTOSEED"] = "0"
os.environ["SMS_PROVIDER"] = "demo"
os.environ["MAP_MODE"] = "synthetic"

import pytest
from fastapi.testclient import TestClient

from app import store
from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        store.clear_all("tests")
        yield c


@pytest.fixture()
def officer(client):
    r = client.post("/api/auth/login", json={"username": "controlroom", "password": "Relief@2026"})
    return {"Authorization": "Bearer " + r.json()["token"]}


def verified_token(client, phone):
    code = client.post("/api/public/otp/request", json={"phone": phone}).json()["demo_code"]
    return client.post("/api/public/otp/verify", json={"phone": phone, "code": code}).json()["token"]
