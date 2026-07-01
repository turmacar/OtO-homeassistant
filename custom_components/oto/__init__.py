"""The OtO Lawn integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import OtOAPI, OtOAuthenticationError
from .const import DOMAIN, POLLING_INTERVAL_SEC

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.CALENDAR,
]
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the OtO Lawn integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OtO Lawn from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    api = OtOAPI(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )

    try:
        logged_in = await hass.async_add_executor_job(api.login)
        if not logged_in:
            raise ConfigEntryAuthFailed("Failed to authenticate with OtO")
    except OtOAuthenticationError as err:
        raise ConfigEntryAuthFailed from err
    except Exception as err:
        raise ConfigEntryNotReady from err

    async def async_update_data():
        """Fetch data from OtO API."""
        try:
            # Get device profiles (deviceId, macAddress, etc.)
            profiles = await hass.async_add_executor_job(api.get_device_profiles)
            if not profiles:
                raise UpdateFailed("No devices found")

            # Get device names from winter mode status endpoint
            device_statuses = await hass.async_add_executor_job(
                api.get_winter_mode_status
            )
            device_names = {
                s["deviceId"]: s.get("deviceName", s["deviceId"])
                for s in device_statuses
                if "deviceId" in s
            }

            result = {}
            for profile in profiles:
                device_id = profile.get("deviceId")
                if not device_id:
                    continue

                status = await hass.async_add_executor_job(
                    api.get_device_status, device_id
                )
                battery = await hass.async_add_executor_job(
                    api.get_device_battery, device_id
                )

                result[device_id] = {
                    "profile": profile,
                    "device_name": device_names.get(device_id, device_id),
                    "status": status or {},
                    "battery": battery or [],
                }

            # Fetch account-level weather forecast
            weather = await hass.async_add_executor_job(api.get_weather_forecast)
            result["_weather"] = weather or {}

            # Fetch frost dates
            frost = await hass.async_add_executor_job(api.get_frost_dates)
            result["_frost"] = frost or {}

            return result
        except OtOAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except Exception as err:
            raise UpdateFailed(f"Error communicating with OtO API: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=POLLING_INTERVAL_SEC),
    )

    await coordinator.async_config_entry_first_refresh()

    # Separate coordinator for device logs — fetched once on startup only.
    # Historical data doesn't change, so no recurring refresh needed.
    # Reload the integration to re-fetch.
    async def async_update_logs():
        """Fetch device logs from OtO API."""
        try:
            profiles = await hass.async_add_executor_job(api.get_device_profiles)
            result = {}
            for profile in (profiles or []):
                device_id = profile.get("deviceId")
                if not device_id:
                    continue
                logs = await hass.async_add_executor_job(
                    api.get_device_logs, device_id
                )
                result[device_id] = logs or []
            return result
        except OtOAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except Exception as err:
            raise UpdateFailed(f"Error fetching device logs: {err}") from err

    logs_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_logs",
        update_method=async_update_logs,
    )

    await logs_coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "logs_coordinator": logs_coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an OtO config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
