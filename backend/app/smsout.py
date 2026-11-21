"""Outgoing SMS. SMS_PROVIDER is demo (sends nothing), fast2sms, or android (your own phone and SIM)."""

from __future__ import annotations
import base64
import json
import os
import urllib.error
import urllib.request

F2S_URL = "https://www.fast2sms.com/dev/bulkV2"


def provider() -> str:
    return os.getenv("SMS_PROVIDER", "demo").strip().lower()


def _otp_text(code: str) -> str:
    return f"Your ResQGrid verification code is {code}. Valid for 5 minutes. Do not share it."


def _post(url: str, body: dict, headers: dict, timeout: int = 20):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        method="POST",
        headers={"Content-Type": "application/json", **headers},
    )
    return urllib.request.urlopen(req, timeout=timeout)


def _fast2sms(phone: str, text: str | None, code: str | None) -> None:
    key = os.getenv("FAST2SMS_API_KEY", "").strip()
    if not key:
        raise RuntimeError("FAST2SMS_API_KEY is not set")
    if code and os.getenv("FAST2SMS_ROUTE", "otp") != "q":
        body = {"route": "otp", "variables_values": code, "numbers": phone}
    else:
        body = {"route": "q", "message": text or _otp_text(code or ""), "numbers": phone}
    try:
        with _post(F2S_URL, body, {"authorization": key, "Accept": "*/*"}) as r:
            resp = json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            resp = json.loads(e.read())
        except Exception:
            raise RuntimeError(f"provider HTTP {e.code}") from None
    except Exception as e:
        raise RuntimeError(f"could not reach the SMS provider: {e}") from e
    if not resp.get("return"):
        raise RuntimeError(f"provider said: {resp.get('message') or resp}")


def _android(phone: str, text: str) -> None:
    """Send through the SMS Gateway for Android app (Local Server mode) on the same network."""
    base = os.getenv("ANDROID_SMS_URL", "").strip().rstrip("/")
    if not base:
        raise RuntimeError("ANDROID_SMS_URL is not set (example: http://192.168.1.5:8080)")
    auth = base64.b64encode(
        f"{os.getenv('ANDROID_SMS_USER', '')}:{os.getenv('ANDROID_SMS_PASS', '')}".encode()
    ).decode()
    to = "+91" + phone
    tries = [
        (base + "/message", {"message": text, "phoneNumbers": [to]}),  # classic local API
        (base + "/messages", {"textMessage": {"text": text}, "phoneNumbers": [to]}),
    ]  # newer API shape
    last = "no response"
    for url, body in tries:
        try:
            with _post(url, body, {"Authorization": "Basic " + auth}, 15) as r:
                if 200 <= r.status < 300:
                    return
                last = f"HTTP {r.status}"
        except urllib.error.HTTPError as e:
            last = f"{url} -> HTTP {e.code} {e.read()[:160].decode(errors='ignore')}"
            if e.code not in (400, 404, 405):
                break
        except Exception as e:
            raise RuntimeError(f"could not reach your phone at {base}: {e}") from e
    raise RuntimeError(f"phone gateway said: {last}")


def send_otp(phone: str, code: str) -> None:
    """Send a one-time code to a 10-digit mobile number. Raises RuntimeError if sending fails."""
    p = provider()
    if p == "fast2sms":
        _fast2sms(phone, None, code)
    elif p == "android":
        _android(phone, _otp_text(code))


def send_text(phone: str, text: str) -> None:
    """Reply to an inbound SMS. Only the phone gateway is used for this, to avoid paid messages."""
    if provider() == "android":
        _android(phone, text)
