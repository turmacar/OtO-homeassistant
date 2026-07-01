"""Tests for OtO API client."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import api module directly to avoid homeassistant dependency.
# Append (not prepend) to sys.path so stdlib modules like 'calendar'
# aren't shadowed by our custom_components/oto/calendar.py.
sys.path.append(str(Path(__file__).resolve().parent.parent / "custom_components" / "oto"))
from api import (  # noqa: E402
    EMS_BASE_URL,
    FIREBASE_API_KEY,
    FIREBASE_AUTH_URL,
    SCHEDULER_BASE_URL,
    OtOAPI,
    OtOAuthenticationError,
)


def test_api_init():
    """Test API client initialization."""
    api = OtOAPI(username="test@example.com", password="testpass")
    assert api._username == "test@example.com"
    assert api._password == "testpass"
    assert api._id_token is None
    assert api._uid is None


def test_login_success():
    """Test successful login."""
    api = OtOAPI(username="test@example.com", password="testpass")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "idToken": "test-token",
        "refreshToken": "test-refresh",
        "localId": "test-uid-123",
        "expiresIn": "3600",
    }
    api._session.post = MagicMock(return_value=mock_response)

    assert api.login() is True
    assert api._id_token == "test-token"
    assert api._uid == "test-uid-123"

    # Verify the correct Firebase Auth endpoint was called
    call_args = api._session.post.call_args
    assert FIREBASE_AUTH_URL in call_args[0][0]
    assert call_args[1]["params"]["key"] == FIREBASE_API_KEY
    assert call_args[1]["json"]["email"] == "test@example.com"


def test_login_invalid_credentials():
    """Test login with invalid credentials."""
    api = OtOAPI(username="bad@example.com", password="wrong")

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {
        "error": {"message": "INVALID_LOGIN_CREDENTIALS"}
    }
    api._session.post = MagicMock(return_value=mock_response)

    with pytest.raises(OtOAuthenticationError, match="Invalid credentials"):
        api.login()


def _make_logged_in_api():
    """Create an API instance that is already logged in."""
    api = OtOAPI(username="test@example.com", password="testpass")
    api._id_token = "test-token"
    api._uid = "test-uid-123"
    api._token_expiry = 9999999999
    return api


def test_get_devices():
    """Test fetching device list from Cloud Run."""
    api = _make_logged_in_api()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {
            "cohortOverride": False,
            "isUpdating": False,
            "notification": ["Device finished watering."],
            "notificationData": [{"id": "abc123", "type": 5}],
        }
    ]
    mock_response.raise_for_status = MagicMock()
    api._session.get = MagicMock(return_value=mock_response)

    devices = api.get_devices()
    assert len(devices) == 1
    assert devices[0]["isUpdating"] is False

    call_args = api._session.get.call_args
    assert f"/account/test-uid-123/devices" in call_args[0][0]
    assert call_args[1]["headers"]["Authorization"] == "Bearer test-token"


def test_get_device_status():
    """Test fetching device status from Cloud Run."""
    api = _make_logged_in_api()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "batteryVoltage_V": 4.22,
        "batteryCurrent_mA": 150.0,
        "version": "v4.3.7-v5-prod",
        "wifiStrength": -62,
        "lastUpdate": "2026-06-30T20:44:58.795403+00:00",
        "scheduleId": None,
        "resetReason": 8,
    }
    api._session.get = MagicMock(return_value=mock_response)

    status = api.get_device_status("oto0000001")
    assert status["batteryVoltage_V"] == 4.22
    assert status["version"] == "v4.3.7-v5-prod"
    assert status["wifiStrength"] == -62

    call_args = api._session.get.call_args
    assert "/device/oto0000001/status" in call_args[0][0]


def test_get_device_status_not_found():
    """Test device status returns None for unknown device."""
    api = _make_logged_in_api()

    mock_response = MagicMock()
    mock_response.status_code = 404
    api._session.get = MagicMock(return_value=mock_response)

    assert api.get_device_status("nonexistent") is None


def test_get_device_battery():
    """Test fetching battery history."""
    api = _make_logged_in_api()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [None, None, 100, 100, 100, 99, 98]
    mock_response.raise_for_status = MagicMock()
    api._session.get = MagicMock(return_value=mock_response)

    battery = api.get_device_battery("oto0000001")
    assert len(battery) == 7
    assert battery[2] == 100
    assert battery[0] is None


def test_get_device_profile():
    """Test fetching device profile."""
    api = _make_logged_in_api()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "activated": True,
        "deviceId": "oto0000001",
        "macAddress": "AA:BB:CC:DD:EE:FF",
        "batchNumber": "5161",
        "bomNumber": "6314-F",
    }
    mock_response.raise_for_status = MagicMock()
    api._session.get = MagicMock(return_value=mock_response)

    profile = api.get_device_profile("oto0000001")
    assert profile["deviceId"] == "oto0000001"
    assert profile["macAddress"] == "AA:BB:CC:DD:EE:FF"

    call_args = api._session.get.call_args
    assert "/device/oto0000001" in call_args[0][0]
    assert "/status" not in call_args[0][0]


def test_get_weather_forecast():
    """Test fetching weather forecast."""
    api = _make_logged_in_api()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "cityName": "Springfield",
        "currentTemperature_C": 14.5,
        "currentWeatherCode": 804,
        "forecastedWeeklyMaxTemperature_C": [20.4, 23.1],
    }
    mock_response.raise_for_status = MagicMock()
    api._session.get = MagicMock(return_value=mock_response)

    forecast = api.get_weather_forecast()
    assert forecast["cityName"] == "Springfield"
    assert forecast["currentTemperature_C"] == 14.5

    call_args = api._session.get.call_args
    assert f"/account/test-uid-123/weather/forecast" in call_args[0][0]


def test_manual_stop():
    """Test manual stop watering."""
    api = _make_logged_in_api()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "ok"}
    mock_response.raise_for_status = MagicMock()
    api._session.post = MagicMock(return_value=mock_response)

    result = api.manual_stop("oto0000001")
    assert result["status"] == "ok"

    call_args = api._session.post.call_args
    assert SCHEDULER_BASE_URL in call_args[0][0]
    assert "/manual-stop" in call_args[0][0]
    body = call_args[1]["json"]
    assert body["uid"] == "test-uid-123"
    assert body["deviceId"] == "oto0000001"


def test_not_logged_in_raises():
    """Test that API calls raise when not logged in."""
    api = OtOAPI(username="test@example.com", password="testpass")

    with pytest.raises(OtOAuthenticationError, match="Not logged in"):
        api.get_devices()
