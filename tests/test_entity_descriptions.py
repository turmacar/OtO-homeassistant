"""Tests for OtO entity description metadata and value functions."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_MISSING = object()


# -- HA stub infrastructure ----------------------------------------


def _install_stub(stubs: dict, name: str, mod: types.ModuleType) -> None:
    stubs.setdefault(name, sys.modules.get(name, _MISSING))
    sys.modules[name] = mod


def _restore_stubs(stubs: dict) -> None:
    for name, prev in reversed(list(stubs.items())):
        if prev is _MISSING:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = prev


def _ensure_module(stubs: dict, name: str, *, package: bool = False) -> types.ModuleType:
    mod = sys.modules.get(name)
    if not isinstance(mod, types.ModuleType):
        mod = types.ModuleType(name)
        _install_stub(stubs, name, mod)
    if package and not hasattr(mod, "__path__"):
        mod.__path__ = []
    return mod


def install_ha_stubs(stubs: dict) -> None:
    """Install minimal HA surface for importing sensor/binary_sensor modules."""
    _ensure_module(stubs, "homeassistant", package=True)
    _ensure_module(stubs, "homeassistant.components", package=True)
    _ensure_module(stubs, "homeassistant.helpers", package=True)

    # homeassistant.components.sensor
    sensor_mod = _ensure_module(stubs, "homeassistant.components.sensor")

    class SensorDeviceClass:
        BATTERY = "battery"
        PRECIPITATION = "precipitation"
        SIGNAL_STRENGTH = "signal_strength"
        TEMPERATURE = "temperature"
        TIMESTAMP = "timestamp"
        VOLTAGE = "voltage"

    @dataclass(frozen=True)
    class SensorEntityDescription:
        key: str
        name: str | None = None
        icon: str | None = None
        native_unit_of_measurement: str | None = None
        device_class: str | None = None
        state_class: str | None = None
        entity_category: str | None = None

    class SensorStateClass:
        MEASUREMENT = "measurement"

    class SensorEntity:
        pass

    sensor_mod.SensorDeviceClass = SensorDeviceClass
    sensor_mod.SensorEntityDescription = SensorEntityDescription
    sensor_mod.SensorStateClass = SensorStateClass
    sensor_mod.SensorEntity = SensorEntity

    # homeassistant.components.binary_sensor
    bs_mod = _ensure_module(stubs, "homeassistant.components.binary_sensor")

    class BinarySensorDeviceClass:
        CONNECTIVITY = "connectivity"
        RUNNING = "running"

    @dataclass(frozen=True)
    class BinarySensorEntityDescription:
        key: str
        name: str | None = None
        icon: str | None = None
        device_class: str | None = None
        entity_category: str | None = None

    class BinarySensorEntity:
        pass

    bs_mod.BinarySensorDeviceClass = BinarySensorDeviceClass
    bs_mod.BinarySensorEntityDescription = BinarySensorEntityDescription
    bs_mod.BinarySensorEntity = BinarySensorEntity

    # homeassistant.const
    const_mod = _ensure_module(stubs, "homeassistant.const")
    const_mod.CONF_PASSWORD = "password"
    const_mod.CONF_USERNAME = "username"
    const_mod.PERCENTAGE = "%"
    const_mod.SIGNAL_STRENGTH_DECIBELS_MILLIWATT = "dBm"

    class UnitOfElectricPotential:
        VOLT = "V"

    class UnitOfPrecipitationDepth:
        MILLIMETERS = "mm"

    class UnitOfTemperature:
        CELSIUS = "°C"

    const_mod.UnitOfElectricPotential = UnitOfElectricPotential
    const_mod.UnitOfPrecipitationDepth = UnitOfPrecipitationDepth
    const_mod.UnitOfTemperature = UnitOfTemperature

    # homeassistant.helpers.entity
    entity_mod = _ensure_module(stubs, "homeassistant.helpers.entity")

    class EntityCategory:
        DIAGNOSTIC = "diagnostic"
        CONFIG = "config"

    entity_mod.EntityCategory = EntityCategory

    # homeassistant.helpers.entity_platform
    ep_mod = _ensure_module(stubs, "homeassistant.helpers.entity_platform")
    ep_mod.AddEntitiesCallback = None

    # homeassistant.helpers.update_coordinator
    uc_mod = _ensure_module(stubs, "homeassistant.helpers.update_coordinator")

    class CoordinatorEntity:
        pass

    class DataUpdateCoordinator:
        pass

    uc_mod.CoordinatorEntity = CoordinatorEntity
    uc_mod.DataUpdateCoordinator = DataUpdateCoordinator

    # homeassistant.config_entries
    ce_mod = _ensure_module(stubs, "homeassistant.config_entries")
    ce_mod.ConfigEntry = None

    # homeassistant.core
    core_mod = _ensure_module(stubs, "homeassistant.core")
    core_mod.HomeAssistant = None


def _load_module(stubs: dict, name: str, path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    _install_stub(stubs, name, mod)
    spec.loader.exec_module(mod)
    return mod


# -- Install stubs and load modules -----------------------------------

_stubs: dict[str, object] = {}
install_ha_stubs(_stubs)

# Set up the oto package so relative imports work
_oto_pkg_path = REPO_ROOT / "custom_components" / "oto"

# Create the package hierarchy: custom_components.oto
_cc = _ensure_module(_stubs, "custom_components", package=True)
_cc.__path__ = [str(REPO_ROOT / "custom_components")]

_oto = _ensure_module(_stubs, "custom_components.oto", package=True)
_oto.__path__ = [str(_oto_pkg_path)]

# Load const first
const_mod = _load_module(
    _stubs, "custom_components.oto.const", _oto_pkg_path / "const.py"
)

sensor_mod = _load_module(
    _stubs, "custom_components.oto.sensor", _oto_pkg_path / "sensor.py"
)
binary_sensor_mod = _load_module(
    _stubs, "custom_components.oto.binary_sensor", _oto_pkg_path / "binary_sensor.py"
)


def tearDownModule() -> None:
    _restore_stubs(_stubs)


# -- Sample data fixtures ------------------------------------------

SAMPLE_DEVICE_DATA = {
    "profile": {"deviceId": "oto1234", "macAddress": "AA:BB:CC:DD:EE:FF"},
    "status": {
        "batteryVoltage_V": 4.15,
        "wifiStrength": -58,
        "version": "4.3.7-v5-prod",
        "lastUpdate": "2026-07-01T12:00:00Z",
        "scheduleId": None,
        "factoryReset": False,
    },
    "battery": [100, 99, None, 98, 97],
}

SAMPLE_DEVICE_WATERING = {
    "profile": {"deviceId": "oto1234"},
    "status": {
        "scheduleId": "sched-abc-123",
        "lastUpdate": "2026-07-01T12:05:00Z",
        "factoryReset": False,
    },
    "battery": [100],
}

SAMPLE_DEVICE_WINTER = {
    "profile": {"deviceId": "oto1234"},
    "status": {
        "lastUpdate": "2026-01-15T08:00:00Z",
        "scheduleId": None,
        "factoryReset": True,
    },
    "battery": [],
}

SAMPLE_LOGS = [
    {
        "eventType": "irrigation_end",
        "title": "Finished watering Zone A",
        "body": "Watered for 12 minutes",
        "createdAt": "2026-06-30T18:30:00Z",
        "zoneId": "zone-1",
        "scheduleId": "sched-abc",
    },
    {
        "eventType": "weather_skip",
        "title": "Rain skip",
        "body": "Skipped due to rain forecast",
        "createdAt": "2026-06-29T06:00:00Z",
        "zoneId": None,
        "scheduleId": "sched-abc",
    },
]

SAMPLE_WEATHER = {
    "currentTemperature_C": 22.5,
    "forecastedHourlyPrecipitation_mm": [1.2, 0.5, 0.0],
    "cityName": "Springfield",
}


# -- Device sensor tests -----------------------------------------


class DeviceSensorDescriptionTests(unittest.TestCase):
    """Validate device sensor descriptions."""

    @classmethod
    def setUpClass(cls):
        cls.sensors = {d.key: d for d in sensor_mod.DEVICE_SENSOR_DESCRIPTIONS}

    def test_all_keys_present(self):
        expected = {"battery", "battery_voltage", "wifi_strength", "firmware", "last_update"}
        self.assertEqual(set(self.sensors.keys()), expected)

    def test_battery_value(self):
        desc = self.sensors["battery"]
        self.assertEqual(desc.value_fn(SAMPLE_DEVICE_DATA), 97)
        self.assertIsNone(desc.entity_category)

    def test_battery_voltage_value(self):
        desc = self.sensors["battery_voltage"]
        self.assertEqual(desc.value_fn(SAMPLE_DEVICE_DATA), 4.15)
        self.assertEqual(desc.entity_category, "diagnostic")

    def test_wifi_strength_value(self):
        desc = self.sensors["wifi_strength"]
        self.assertEqual(desc.value_fn(SAMPLE_DEVICE_DATA), -58)

    def test_firmware_value(self):
        desc = self.sensors["firmware"]
        self.assertEqual(desc.value_fn(SAMPLE_DEVICE_DATA), "4.3.7-v5-prod")

    def test_last_update_returns_datetime(self):
        desc = self.sensors["last_update"]
        result = desc.value_fn(SAMPLE_DEVICE_DATA)
        self.assertIsInstance(result, datetime)
        self.assertIsNotNone(result.tzinfo)

    def test_battery_empty_list(self):
        desc = self.sensors["battery"]
        self.assertIsNone(desc.value_fn({"battery": []}))

    def test_battery_all_none(self):
        desc = self.sensors["battery"]
        self.assertIsNone(desc.value_fn({"battery": [None, None]}))

    def test_missing_status_returns_none(self):
        desc = self.sensors["battery_voltage"]
        self.assertIsNone(desc.value_fn({}))


# -- Log sensor tests -----------------------------------------


class LogSensorDescriptionTests(unittest.TestCase):
    """Validate log sensor descriptions."""

    @classmethod
    def setUpClass(cls):
        cls.sensors = {d.key: d for d in sensor_mod.LOG_SENSOR_DESCRIPTIONS}

    def test_all_keys_present(self):
        expected = {"last_watering_event", "last_watering_time"}
        self.assertEqual(set(self.sensors.keys()), expected)

    def test_last_watering_event_value(self):
        desc = self.sensors["last_watering_event"]
        self.assertEqual(desc.value_fn(SAMPLE_LOGS), "Finished watering Zone A")

    def test_last_watering_event_extra_attrs(self):
        desc = self.sensors["last_watering_event"]
        attrs = desc.extra_attrs_fn(SAMPLE_LOGS)
        self.assertEqual(attrs["body"], "Watered for 12 minutes")
        self.assertEqual(attrs["event_type"], "irrigation_end")

    def test_last_watering_time_returns_datetime(self):
        desc = self.sensors["last_watering_time"]
        result = desc.value_fn(SAMPLE_LOGS)
        self.assertIsInstance(result, datetime)

    def test_empty_logs_returns_none(self):
        desc = self.sensors["last_watering_event"]
        self.assertIsNone(desc.value_fn([]))

    def test_no_irrigation_logs_returns_none(self):
        non_irrigation = [{"eventType": "device_boot", "title": "Boot"}]
        desc = self.sensors["last_watering_event"]
        self.assertIsNone(desc.value_fn(non_irrigation))


# -- Weather sensor tests -----------------------------------------


class WeatherSensorDescriptionTests(unittest.TestCase):
    """Validate weather sensor descriptions."""

    @classmethod
    def setUpClass(cls):
        cls.sensors = {d.key: d for d in sensor_mod.WEATHER_SENSOR_DESCRIPTIONS}

    def test_all_keys_present(self):
        expected = {"temperature", "precipitation", "location", "first_frost", "last_frost"}
        self.assertEqual(set(self.sensors.keys()), expected)

    def test_temperature_value(self):
        desc = self.sensors["temperature"]
        self.assertEqual(desc.value_fn(SAMPLE_WEATHER), 22.5)
        self.assertIsNone(desc.entity_category)

    def test_precipitation_value(self):
        desc = self.sensors["precipitation"]
        self.assertEqual(desc.value_fn(SAMPLE_WEATHER), 1.2)

    def test_precipitation_empty_forecast(self):
        desc = self.sensors["precipitation"]
        self.assertIsNone(desc.value_fn({"forecastedHourlyPrecipitation_mm": []}))

    def test_location_value(self):
        desc = self.sensors["location"]
        self.assertEqual(desc.value_fn(SAMPLE_WEATHER), "Springfield")
        self.assertEqual(desc.entity_category, "diagnostic")

    def test_frost_sensors_have_no_value_fn(self):
        for key in ("first_frost", "last_frost"):
            desc = self.sensors[key]
            self.assertIsNone(desc.value_fn)


# -- Binary sensor tests -----------------------------------------


class BinarySensorDescriptionTests(unittest.TestCase):
    """Validate binary sensor descriptions."""

    @classmethod
    def setUpClass(cls):
        cls.sensors = {d.key: d for d in binary_sensor_mod.BINARY_SENSOR_DESCRIPTIONS}

    def test_all_keys_present(self):
        expected = {"connected", "watering", "winter_mode"}
        self.assertEqual(set(self.sensors.keys()), expected)

    def test_connected_when_has_last_update(self):
        desc = self.sensors["connected"]
        self.assertTrue(desc.is_on_fn(SAMPLE_DEVICE_DATA))
        self.assertEqual(desc.entity_category, "diagnostic")

    def test_connected_when_no_status(self):
        desc = self.sensors["connected"]
        self.assertFalse(desc.is_on_fn({}))

    def test_watering_when_no_schedule(self):
        desc = self.sensors["watering"]
        self.assertFalse(desc.is_on_fn(SAMPLE_DEVICE_DATA))
        self.assertIsNone(desc.entity_category)

    def test_watering_when_active_schedule(self):
        desc = self.sensors["watering"]
        self.assertTrue(desc.is_on_fn(SAMPLE_DEVICE_WATERING))

    def test_winter_mode_off(self):
        desc = self.sensors["winter_mode"]
        self.assertFalse(desc.is_on_fn(SAMPLE_DEVICE_DATA))

    def test_winter_mode_on(self):
        desc = self.sensors["winter_mode"]
        self.assertTrue(desc.is_on_fn(SAMPLE_DEVICE_WINTER))


if __name__ == "__main__":
    unittest.main()
