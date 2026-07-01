"""Binary sensor platform for OtO Lawn integration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


# ── Entity description dataclass ──────────────────────────────────


@dataclass(frozen=True, kw_only=True)
class OtOBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes an OtO binary sensor entity."""

    is_on_fn: Callable[[dict], bool]


# ── Binary sensor descriptions ────────────────────────────────────

BINARY_SENSOR_DESCRIPTIONS: tuple[OtOBinarySensorEntityDescription, ...] = (
    OtOBinarySensorEntityDescription(
        key="connected",
        name="Connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: bool(data.get("status", {}).get("lastUpdate")),
    ),
    OtOBinarySensorEntityDescription(
        key="watering",
        name="Watering",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:sprinkler-variant",
        entity_category=None,
        is_on_fn=lambda data: data.get("status", {}).get("scheduleId") is not None,
    ),
    OtOBinarySensorEntityDescription(
        key="winter_mode",
        name="Winter Mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: data.get("status", {}).get("factoryReset", False),
    ),
)


# ── Platform setup ────────────────────────────────────────────────


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OtO binary sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = []
    for device_id, device_data in coordinator.data.items():
        if not isinstance(device_data, dict) or "profile" not in device_data:
            continue
        device_name = device_data.get("device_name", device_id)

        for desc in BINARY_SENSOR_DESCRIPTIONS:
            entities.append(
                OtOBinarySensor(coordinator, desc, device_id, device_name)
            )

    async_add_entities(entities)


# ── Entity class ──────────────────────────────────────────────────


class OtOBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for OtO device data."""

    entity_description: OtOBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: OtOBinarySensorEntityDescription,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the binary sensor."""
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
    def is_on(self) -> bool:
        """Return the binary sensor state."""
        if self.coordinator.data and self._device_id in self.coordinator.data:
            return self.entity_description.is_on_fn(
                self.coordinator.data[self._device_id]
            )
        return False
