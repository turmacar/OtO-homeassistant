"""OtO Lawn API client — Firebase Auth + Cloud Run REST API."""

from __future__ import annotations

import logging
import time

import requests

_LOGGER = logging.getLogger(__name__)

FIREBASE_API_KEY = "AIzaSyBlkDTR_GZSnGJuXdWAtH65ceeXyHtSrIs"
FIREBASE_AUTH_URL = "https://identitytoolkit.googleapis.com/v1/accounts"

EMS_BASE_URL = "https://oto-cloud-service-ems-prod-716180884817.us-central1.run.app"
SCHEDULER_BASE_URL = "https://oto-cloud-service-scheduler-prod-716180884817.us-central1.run.app"


class OtOAuthenticationError(Exception):
    """Raised when authentication with OtO API fails."""


class OtOAPIError(Exception):
    """Raised when an OtO API request fails."""


class OtOAPI:
    """Client for OtO Lawn via Firebase Auth + Cloud Run REST API."""

    def __init__(self, username: str, password: str) -> None:
        """Initialize the API client."""
        self._username = username
        self._password = password
        self._session = requests.Session()
        self._id_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expiry: float = 0
        self._uid: str | None = None

    @property
    def uid(self) -> str | None:
        """Return the Firebase UID."""
        return self._uid

    @property
    def _auth_headers(self) -> dict[str, str]:
        """Get authorization headers for Cloud Run requests."""
        return {"Authorization": f"Bearer {self._id_token}"}

    def _ensure_token(self) -> None:
        """Refresh the ID token if expired."""
        if self._id_token and time.time() < self._token_expiry - 60:
            return
        if self._refresh_token:
            self._refresh_id_token()
        else:
            raise OtOAuthenticationError("Not logged in")

    def login(self) -> bool:
        """Authenticate with Firebase Auth using email/password."""
        try:
            response = self._session.post(
                f"{FIREBASE_AUTH_URL}:signInWithPassword",
                params={"key": FIREBASE_API_KEY},
                json={
                    "email": self._username,
                    "password": self._password,
                    "returnSecureToken": True,
                },
                timeout=30,
            )

            if response.status_code == 400:
                error = response.json().get("error", {})
                msg = error.get("message", "Unknown error")
                if msg in ("EMAIL_NOT_FOUND", "INVALID_PASSWORD", "INVALID_LOGIN_CREDENTIALS"):
                    raise OtOAuthenticationError(f"Invalid credentials: {msg}")
                raise OtOAuthenticationError(f"Auth error: {msg}")

            response.raise_for_status()
            data = response.json()

            self._id_token = data["idToken"]
            self._refresh_token = data["refreshToken"]
            self._uid = data["localId"]
            self._token_expiry = time.time() + int(data.get("expiresIn", 3600))

            _LOGGER.debug("OtO login successful for uid=%s", self._uid)
            return True

        except OtOAuthenticationError:
            raise
        except requests.exceptions.RequestException as err:
            raise OtOAPIError(f"Login request failed: {err}") from err

    def _refresh_id_token(self) -> None:
        """Refresh the Firebase ID token using the refresh token."""
        try:
            response = self._session.post(
                "https://securetoken.googleapis.com/v1/token",
                params={"key": FIREBASE_API_KEY},
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            self._id_token = data["id_token"]
            self._refresh_token = data["refresh_token"]
            self._uid = data["user_id"]
            self._token_expiry = time.time() + int(data.get("expires_in", 3600))

        except requests.exceptions.RequestException as err:
            raise OtOAuthenticationError(f"Token refresh failed: {err}") from err

    def _ems_get(self, path: str) -> requests.Response:
        """GET from the EMS Cloud Run service."""
        self._ensure_token()
        try:
            response = self._session.get(
                f"{EMS_BASE_URL}{path}",
                headers=self._auth_headers,
                timeout=30,
            )
            if response.status_code == 403:
                raise OtOAuthenticationError("Access denied")
            return response
        except OtOAuthenticationError:
            raise
        except requests.exceptions.RequestException as err:
            raise OtOAPIError(f"EMS request failed: {err}") from err

    def _scheduler_post(self, path: str, body: dict) -> requests.Response:
        """POST to the Scheduler Cloud Run service."""
        self._ensure_token()
        try:
            response = self._session.post(
                f"{SCHEDULER_BASE_URL}{path}",
                headers=self._auth_headers,
                json=body,
                timeout=30,
            )
            if response.status_code == 403:
                raise OtOAuthenticationError("Access denied")
            return response
        except OtOAuthenticationError:
            raise
        except requests.exceptions.RequestException as err:
            raise OtOAPIError(f"Scheduler request failed: {err}") from err

    # ── Device endpoints (EMS service) ────────────────────────────

    def get_devices(self) -> list[dict]:
        """Fetch all devices for this account."""
        if not self._uid:
            raise OtOAuthenticationError("Not logged in")
        response = self._ems_get(f"/account/{self._uid}/devices")
        response.raise_for_status()
        return response.json()

    def get_device_profiles(self) -> list[dict]:
        """Fetch all device profiles for this account."""
        if not self._uid:
            raise OtOAuthenticationError("Not logged in")
        response = self._ems_get(f"/devices/{self._uid}")
        response.raise_for_status()
        return response.json()

    def get_device_status(self, device_id: str) -> dict | None:
        """Fetch current status for a device."""
        response = self._ems_get(f"/device/{device_id}/status")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def get_device_profile(self, device_id: str) -> dict | None:
        """Fetch profile for a single device."""
        response = self._ems_get(f"/device/{device_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def get_device_battery(self, device_id: str) -> list | None:
        """Fetch battery history for a device. Returns array of percentage values."""
        response = self._ems_get(f"/device/{device_id}/battery")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    # ── Weather endpoints (EMS service) ───────────────────────────

    def get_weather_forecast(self) -> dict | None:
        """Fetch weather forecast for the account location."""
        if not self._uid:
            raise OtOAuthenticationError("Not logged in")
        response = self._ems_get(f"/account/{self._uid}/weather/forecast")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def get_frost_dates(self) -> dict | None:
        """Fetch first/last frost dates for the account location."""
        if not self._uid:
            raise OtOAuthenticationError("Not logged in")
        response = self._ems_get(f"/account/{self._uid}/weather/frost_dates")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    # ── Device logs (EMS service) ─────────────────────────────────

    def get_device_logs(self, device_id: str) -> list[dict]:
        """Fetch device log history (watering events, skips, errors)."""
        if not self._uid:
            raise OtOAuthenticationError("Not logged in")
        response = self._ems_get(
            f"/account/{self._uid}/device/{device_id}/device_logs"
        )
        if response.status_code == 404:
            return []
        response.raise_for_status()
        return response.json()

    # ── Winter mode (EMS service) ─────────────────────────────────

    def get_winter_mode_status(self) -> list[dict]:
        """Fetch winter mode status for all devices."""
        if not self._uid:
            raise OtOAuthenticationError("Not logged in")
        response = self._ems_get(f"/account/{self._uid}/devices/status")
        response.raise_for_status()
        return response.json()

    # ── Watering control (Scheduler service) ──────────────────────

    def manual_start(self, device_id: str, **kwargs) -> dict:
        """Start manual watering."""
        if not self._uid:
            raise OtOAuthenticationError("Not logged in")
        body = {"uid": self._uid, "bayNumber": 0, **kwargs}
        response = self._scheduler_post("/manual-start", body)
        response.raise_for_status()
        return response.json()

    def manual_stop(self, device_id: str) -> dict:
        """Stop manual watering."""
        if not self._uid:
            raise OtOAuthenticationError("Not logged in")
        body = {"uid": self._uid, "deviceId": device_id}
        response = self._scheduler_post("/manual-stop", body)
        response.raise_for_status()
        return response.json()

    def stop_watering(self, device_id: str) -> bool:
        """Stop watering. Not yet implemented."""
        raise NotImplementedError
