"""Live tests for OtO Cloud Run API endpoints.

These tests hit the real Cloud Run services with a real Firebase token.
They are meant to be run manually during development to discover the API,
not as part of CI.

Usage:
    # Run all discovery tests
    python -m pytest tests/test_cloud_run.py -v -s

    # Run a specific test
    python -m pytest tests/test_cloud_run.py::test_scheduler_schedule_history -v -s

    # Run only the tests that passed last time
    python -m pytest tests/test_cloud_run.py -v -s --lf
"""

import json
import sys
import os

import pytest
import requests

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

FIREBASE_API_KEY = "AIzaSyBlkDTR_GZSnGJuXdWAtH65ceeXyHtSrIs"
FIREBASE_AUTH_URL = (
    f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
    f"?key={FIREBASE_API_KEY}"
)

SCHED = "https://oto-cloud-service-scheduler-prod-716180884817.us-central1.run.app"
EMS = "https://oto-cloud-service-ems-prod-716180884817.us-central1.run.app"
UNIT = "https://oto-cloud-service-unitcall-prod-716180884817.us-central1.run.app"

# Credentials - read from env or fall back to hardcoded (dev only)
OTO_EMAIL = os.environ.get("OTO_EMAIL", "")
OTO_PASSWORD = os.environ.get("OTO_PASSWORD", "")


@pytest.fixture(scope="module")
def auth():
    """Authenticate once per test module. Returns dict with token, uid, headers."""
    resp = requests.post(
        FIREBASE_AUTH_URL,
        json={
            "email": OTO_EMAIL,
            "password": OTO_PASSWORD,
            "returnSecureToken": True,
        },
        timeout=15,
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    data = resp.json()
    token = data["idToken"]
    uid = data["localId"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    print(f"\n  Authenticated as UID: {uid}")
    return {"token": token, "uid": uid, "headers": headers}


def _dump(label, resp):
    """Pretty-print a response for debugging."""
    print(f"\n  [{resp.status_code}] {label}")
    try:
        print(f"  {json.dumps(resp.json(), indent=2)[:2000]}")
    except Exception:
        print(f"  {resp.text[:2000]}")


# ---------------------------------------------------------------------------
# Scheduler service
# ---------------------------------------------------------------------------


class TestScheduler:
    """Tests for the scheduler Cloud Run service."""

    def test_health(self, auth):
        r = requests.get(f"{SCHED}/health", timeout=10)
        _dump("scheduler /health", r)
        assert r.status_code == 200

    def test_schedule_history_get(self, auth):
        r = requests.get(f"{SCHED}/schedule/history", headers=auth["headers"], timeout=10)
        _dump("GET /schedule/history", r)

    def test_schedule_history_get_with_uid(self, auth):
        r = requests.get(
            f"{SCHED}/schedule/history",
            headers=auth["headers"],
            params={"accountId": auth["uid"]},
            timeout=10,
        )
        _dump("GET /schedule/history?accountId=uid", r)

    def test_schedule_history_post_empty(self, auth):
        r = requests.post(
            f"{SCHED}/schedule/history",
            headers=auth["headers"],
            json={},
            timeout=10,
        )
        _dump("POST /schedule/history {}", r)

    def test_schedule_history_post_with_uid(self, auth):
        r = requests.post(
            f"{SCHED}/schedule/history",
            headers=auth["headers"],
            json={"accountId": auth["uid"]},
            timeout=10,
        )
        _dump("POST /schedule/history {accountId}", r)

    def test_routine_get(self, auth):
        r = requests.get(f"{SCHED}/routine", headers=auth["headers"], timeout=10)
        _dump("GET /routine", r)

    def test_zones_group_get(self, auth):
        r = requests.get(f"{SCHED}/zones/group", headers=auth["headers"], timeout=10)
        _dump("GET /zones/group", r)

    def test_zones_groups_get(self, auth):
        r = requests.get(f"{SCHED}/zones/groups", headers=auth["headers"], timeout=10)
        _dump("GET /zones/groups", r)

    def test_weather_forecasted_get(self, auth):
        r = requests.get(f"{SCHED}/weather/forecasted", headers=auth["headers"], timeout=10)
        _dump("GET /weather/forecasted", r)

    def test_weather_frost_dates_get(self, auth):
        r = requests.get(f"{SCHED}/weather/frost_dates", headers=auth["headers"], timeout=10)
        _dump("GET /weather/frost_dates", r)

    def test_manual_start_get(self, auth):
        """GET to see if it reveals expected params (don't actually POST to start watering)."""
        r = requests.get(f"{SCHED}/manual-start", headers=auth["headers"], timeout=10)
        _dump("GET /manual-start", r)

    def test_manual_stop_get(self, auth):
        r = requests.get(f"{SCHED}/manual-stop", headers=auth["headers"], timeout=10)
        _dump("GET /manual-stop", r)


# ---------------------------------------------------------------------------
# EMS service
# ---------------------------------------------------------------------------


class TestEMS:
    """Tests for the EMS (event/message) Cloud Run service."""

    def test_health(self, auth):
        r = requests.get(f"{EMS}/health", timeout=10)
        _dump("ems /health", r)
        assert r.status_code == 200

    def test_messages_get(self, auth):
        r = requests.get(f"{EMS}/messages", headers=auth["headers"], timeout=10)
        _dump("GET /messages", r)

    def test_notification_get(self, auth):
        r = requests.get(f"{EMS}/notification", headers=auth["headers"], timeout=10)
        _dump("GET /notification", r)

    def test_account_device_log_get(self, auth):
        r = requests.get(f"{EMS}/account/device_log", headers=auth["headers"], timeout=10)
        _dump("GET /account/device_log", r)

    def test_message_diagnostic_get(self, auth):
        r = requests.get(f"{EMS}/message/diagnostic", headers=auth["headers"], timeout=10)
        _dump("GET /message/diagnostic", r)


# ---------------------------------------------------------------------------
# Unitcall service
# ---------------------------------------------------------------------------


class TestUnitcall:
    """Tests for the unitcall Cloud Run service (normally device-only)."""

    def test_health(self, auth):
        r = requests.get(f"{UNIT}/health", timeout=10)
        _dump("unitcall /health", r)
        assert r.status_code == 200

    def test_device_status_get(self, auth):
        r = requests.get(
            f"{UNIT}/platforms/device/devices/status",
            headers=auth["headers"],
            timeout=10,
        )
        _dump("GET /platforms/device/devices/status", r)

    def test_device_status_post_empty(self, auth):
        r = requests.post(
            f"{UNIT}/platforms/device/devices/status",
            headers=auth["headers"],
            json={},
            timeout=10,
        )
        _dump("POST /platforms/device/devices/status {}", r)

    def test_battery_get(self, auth):
        r = requests.get(f"{UNIT}/battery", headers=auth["headers"], timeout=10)
        _dump("GET /battery", r)

    def test_battery_post_empty(self, auth):
        r = requests.post(
            f"{UNIT}/battery",
            headers=auth["headers"],
            json={},
            timeout=10,
        )
        _dump("POST /battery {}", r)


# ---------------------------------------------------------------------------
# Exploratory - try common REST patterns
# ---------------------------------------------------------------------------


class TestExplore:
    """Try variations to discover the correct request format."""

    @pytest.mark.parametrize(
        "service,path",
        [
            (SCHED, "/api/schedule/history"),
            (SCHED, "/v1/schedule/history"),
            (SCHED, "/api/v1/schedule/history"),
            (SCHED, f"/schedule/history/{{}}/"),  # placeholder
            (EMS, "/api/messages"),
            (EMS, "/v1/messages"),
            (UNIT, "/api/platforms/device/devices/status"),
            (UNIT, "/device/status"),
            (UNIT, "/status"),
        ],
    )
    def test_alternate_paths(self, auth, service, path):
        """Try alternate URL patterns to find the right one."""
        path = path.replace("{}", auth["uid"])
        r = requests.get(f"{service}{path}", headers=auth["headers"], timeout=10)
        _dump(f"GET {path}", r)

    @pytest.mark.parametrize(
        "service,path,body",
        [
            (SCHED, "/schedule/history", {"uid": "placeholder"}),
            (SCHED, "/routine", {"accountId": "placeholder"}),
            (SCHED, "/zones/group", {"accountId": "placeholder"}),
            (EMS, "/messages", {"accountId": "placeholder"}),
            (EMS, "/notification", {"accountId": "placeholder"}),
            (UNIT, "/platforms/device/devices/status", {"deviceId": "placeholder"}),
            (UNIT, "/battery", {"deviceId": "placeholder"}),
        ],
    )
    def test_post_with_uid_body(self, auth, service, path, body):
        """Try POST with accountId/uid in body."""
        for key in body:
            body[key] = auth["uid"]
        r = requests.post(
            f"{service}{path}",
            headers=auth["headers"],
            json=body,
            timeout=10,
        )
        _dump(f"POST {path} {body}", r)
