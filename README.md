# OtO Lawn - Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Custom [Home Assistant](https://www.home-assistant.io/) integration for [OtO Lawn](https://otolawn.com/) smart sprinklers.

Communicates via OtO's Cloud Run REST API.

## Features

### Sensors

| Entity | Type | Category | Description |
|--------|------|----------|-------------|
| Battery | sensor | Primary | Battery level (%) |
| Battery Voltage | sensor | Diagnostic | Battery voltage (V) |
| WiFi Strength | sensor | Diagnostic | WiFi signal strength (dBm) |
| Firmware | sensor | Diagnostic | Current firmware version |
| Last Update | sensor | Diagnostic | Last device check-in timestamp |
| Last Watering Event | sensor | Primary | Title of most recent watering/skip event |
| Last Watering Time | sensor | Primary | Timestamp of most recent watering event |
| Temperature | sensor | Primary | Current temperature at device location (°C) |
| Precipitation | sensor | Primary | Current hour forecasted precipitation (mm) |
| Location | sensor | Diagnostic | City name from weather API |
| First Frost | sensor | Primary | Predicted first frost date |
| Last Frost | sensor | Primary | Predicted last frost date |

### Binary Sensors

| Entity | Type | Category | Description |
|--------|------|----------|-------------|
| Connected | binary_sensor | Diagnostic | Device connectivity (based on last check-in) |
| Watering | binary_sensor | Primary | Currently watering (active schedule) |
| Winter Mode | binary_sensor | Diagnostic | Device is winterized |

### Calendar

| Entity | Description |
|--------|-------------|
| OtO Watering History | Historical watering events with paired start/end times, rain skips, and errors |

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu -> **Custom repositories**
3. Add `https://github.com/turmacar/OtO-homeassistant` as an **Integration**
4. Search for "OtO Lawn" and install
5. Restart Home Assistant
6. Go to **Settings -> Integrations -> Add Integration -> OtO Lawn**

### Manual

1. Copy `custom_components/oto/` to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant
3. Go to **Settings -> Integrations -> Add Integration -> OtO Lawn**

## Configuration

Enter your OtO Lawn app credentials (email and password) when prompted. The integration will discover all devices on your account.

## Device Notes

- OtO devices are battery-powered and sleep aggressively - they check in with the cloud approximately every **5 minutes**
- Pressing the physical button on the OtO forces an immediate cloud connection
- This integration polls at the same 5-minute interval to match device behavior
- Watering history is fetched once on startup; reload the integration to refresh

## Development

```bash
# Clone and set up
git clone https://github.com/turmacar/OtO-homeassistant.git
cd OtO-homeassistant
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run tests
python -m pytest -v
```

## Related Projects

- [jackery-homeassistant](https://github.com/turmacar/jackery-homeassistant) - Similar cloud API integration for Jackery power stations
- [oto-pi](https://github.com/denmatfoton/oto-pi) - C++ program for driving OtO hardware directly via Raspberry Pi Zero

## License

MIT
