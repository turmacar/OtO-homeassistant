"""Diagnostics support for OtO Lawn integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

REDACT_KEYS = {"password", "username", "email", "uid", "idToken", "refreshToken"}


def _redact(data: Any) -> Any:
    """Recursively redact sensitive values from a data structure."""
    if isinstance(data, dict):
        return {
            k: "**REDACTED**" if k in REDACT_KEYS else _redact(v)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [_redact(item) for item in data]
    return data


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    logs_coordinator = data["logs_coordinator"]

    return {
        "config_entry": {
            "title": entry.title,
            "domain": entry.domain,
            "version": entry.version,
        },
        "coordinator_data": _redact(coordinator.data) if coordinator.data else None,
        "logs_coordinator_data": (
            _redact(logs_coordinator.data) if logs_coordinator.data else None
        ),
    }
