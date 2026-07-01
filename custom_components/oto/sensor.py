"""Sensor platform for OtO Lawn integration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfElectricPotential,
    UnitOfPrecipitationDepth,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _parse_timestamp(raw: Any) -> datetime | None:
    """Parse an ISO timestamp string into a timezone-aware datetime."""
    if raw is None:
        return None
    if isinstance(raw, str):
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    return raw


def _last_non_null(values: list) -> Any:
    """Return the last non-null value from a list."""
    for val in reversed(values):
        if val is not None:
            return val
    return None


def _first_irrigation_log(logs: list[dict]) -> dict | None:
    """Return the most recent irrigation or weather_skip log entry."""
    for log in logs:
        event_type = log.get("eventType", "")
        if "irrigation" in event_type or "weather_skip" in event_type:
            return log
    return None


# ── Entity description dataclass ──────────────────────────────────


@dataclass(frozen=True, kw_only=True)
class OtOSensorEntityDescription(SensorEntityDescription):
    """Describes an OtO sensor entity."""

    value_fn: Callable[[dict], Any] | None = None
    extra_attrs_fn: Callable[[dict], dict | None] | None = None


# ── Device sensor descriptions ────────────────────────────────────
# These read from the main coordinator's per-device data:
# {"profile": {...}, "status": {...}, "battery": [...]}

DEVICE_SENSOR_DESCRIPTIONS: tuple[OtOSensorEntityDescription, ...] = (
    OtOSensorEntityDescription(
        key="battery",
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=None,
        value_fn=lambda data: _last_non_null(data.get("battery", [])),
    ),
    OtOSensorEntityDescription(
        key="battery_voltage",
        name="Battery Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("status", {}).get("batteryVoltage_V"),
    ),
    OtOSensorEntityDescription(
        key="wifi_strength",
        name="WiFi Strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("status", {}).get("wifiStrength"),
    ),
    OtOSensorEntityDescription(
        key="firmware",
        name="Firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("status", {}).get("version"),
    ),
    OtOSensorEntityDescription(
        key="last_update",
        name="Last Update",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _parse_timestamp(
            data.get("status", {}).get("lastUpdate")
        ),
    ),
)


# ── Log sensor descriptions ──────────────────────────────────────
# These read from the logs coordinator's per-device data: [log_entries]

LOG_SENSOR_DESCRIPTIONS: tuple[OtOSensorEntityDescription, ...] = (
    OtOSensorEntityDescription(
        key="last_watering_event",
        name="Last Watering Event",
        icon="mdi:sprinkler-variant",
        entity_category=None,
        value_fn=lambda logs: (
            log.get("title") if (log := _first_irrigation_log(logs)) else None
        ),
        extra_attrs_fn=lambda logs: (
            {
                "body": log.get("body"),
                "event_type": log.get("eventType"),
                "zone_id": log.get("zoneId"),
                "schedule_id": log.get("scheduleId"),
            }
            if (log := _first_irrigation_log(logs))
            else None
        ),
    ),
    OtOSensorEntityDescription(
        key="last_watering_time",
        name="Last Watering Time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:sprinkler-variant",
        entity_category=None,
        value_fn=lambda logs: (
            _parse_timestamp(log.get("createdAt"))
            if (log := _first_irrigation_log(logs))
            else None
        ),
    ),
)


# ── Weather sensor descriptions ──────────────────────────────────
# These read from the main coordinator's account-level _weather dict.

WEATHER_SENSOR_DESCRIPTIONS: tuple[OtOSensorEntityDescription, ...] = (
    OtOSensorEntityDescription(
        key="temperature",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:sun-thermometer",
        entity_category=None,
        value_fn=lambda data: data.get("currentTemperature_C"),
    ),
    OtOSensorEntityDescription(
        key="precipitation",
        name="Precipitation",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        icon="mdi:water-percent",
        entity_category=None,
        value_fn=lambda data: (
            hourly[0]
            if (hourly := data.get("forecastedHourlyPrecipitation_mm", []))
            else None
        ),
    ),
    OtOSensorEntityDescription(
        key="location",
        name="Location",
        icon="mdi:home-map-marker",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("cityName"),
    ),
    OtOSensorEntityDescription(
        key="first_frost",
        name="First Frost",
        icon="mdi:snowflake",
        entity_category=None,
    ),
    OtOSensorEntityDescription(
        key="last_frost",
        name="Last Frost",
        icon="mdi:snowflake",
        entity_category=None,
    ),
)


# ── Platform setup ────────────────────────────────────────────────


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OtO sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    logs_coordinator = hass.data[DOMAIN][entry.entry_id]["logs_coordinator"]

    entities: list[SensorEntity] = []
    first_device_id = None
    first_device_name = None

    for device_id, device_data in coordinator.data.items():
        if not isinstance(device_data, dict) or "profile" not in device_data:
            continue
        if first_device_id is None:
            first_device_id = device_id
            first_device_name = device_data.get("device_name", device_id)
        device_name = device_data.get("device_name", device_id)

        for desc in DEVICE_SENSOR_DESCRIPTIONS:
            entities.append(
                OtODeviceSensor(coordinator, desc, device_id, device_name)
            )
        for desc in LOG_SENSOR_DESCRIPTIONS:
            entities.append(
                OtODeviceSensor(logs_coordinator, desc, device_id, device_name)
            )

    # Account-level weather/frost sensors (attached to first device)
    if first_device_id:
        for desc in WEATHER_SENSOR_DESCRIPTIONS:
            entities.append(
                OtOWeatherSensor(
                    coordinator, desc, first_device_id, first_device_name
                )
            )

    async_add_entities(entities)


# ── Entity classes ────────────────────────────────────────────────


class OtODeviceSensor(CoordinatorEntity, SensorEntity):
    """Sensor for per-device OtO data (status, battery, or logs)."""

    entity_description: OtOSensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: OtOSensorEntityDescription,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device_id = device_id
        self._attr_unique_id = f"oto_{device_id}_{description.key}"
        self._attr_name = f"{device_name} {description.name}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": device_name,
            "manufacturer": "OtO Lawn",
            "model": "OtO Smart Sprinkler",
        }

    @property
    def _device_data(self) -> Any:
        """Get this device's data from the coordinator."""
        if self.coordinator.data and self._device_id in self.coordinator.data:
            return self.coordinator.data[self._device_id]
        return {}

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        if self.entity_description.value_fn:
            return self.entity_description.value_fn(self._device_data)
        return None

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return extra state attributes if defined."""
        if self.entity_description.extra_attrs_fn:
            return self.entity_description.extra_attrs_fn(self._device_data)
        return None


class OtOWeatherSensor(CoordinatorEntity, SensorEntity):
    """Sensor for account-level OtO weather/frost data."""

    entity_description: OtOSensorEntityDescription

    _FROST_FIELDS = {"first_frost": "firstFrostDate", "last_frost": "lastFrostDate"}

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: OtOSensorEntityDescription,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the weather sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"oto_weather_{description.key}"
        self._attr_name = f"{device_name} {description.name}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": device_name,
            "manufacturer": "OtO Lawn",
            "model": "OtO Smart Sprinkler",
        }

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        if not self.coordinator.data:
            return None

        # Frost date sensors read from _frost
        frost_field = self._FROST_FIELDS.get(self.entity_description.key)
        if frost_field:
            return self.coordinator.data.get("_frost", {}).get(frost_field)

        # Weather sensors read from _weather
        if self.entity_description.value_fn:
            weather = self.coordinator.data.get("_weather", {})
            return self.entity_description.value_fn(weather)
        return None
