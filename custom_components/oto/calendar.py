"""Calendar platform for OtO Lawn integration - watering history."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OtO calendar from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    logs_coordinator = hass.data[DOMAIN][entry.entry_id]["logs_coordinator"]

    # Build device name lookup from the main coordinator
    device_names = {}
    for device_id, device_data in coordinator.data.items():
        if not isinstance(device_data, dict) or "profile" not in device_data:
            continue
        device_names[device_id] = device_data.get("device_name", device_id)

    if device_names:
        async_add_entities([
            OtOWateringCalendar(logs_coordinator, device_names)
        ])


def _parse_dt(raw: str) -> datetime:
    """Parse an ISO datetime string, ensuring timezone info."""
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _extract_zone_name(body: str, device_name: str) -> str | None:
    """Extract zone name from log body text.

    Body format: "<device> began watering <zone name>. ..."
    or: "<device> finished watering <zone name>."
    """
    for keyword in ("watering ", "watering of "):
        idx = body.find(keyword)
        if idx >= 0:
            rest = body[idx + len(keyword):]
            # Zone name ends at the period
            dot = rest.find(".")
            if dot >= 0:
                return rest[:dot].strip()
            return rest.strip()
    return None


def _build_calendar_events(
    logs: list[dict], device_name: str
) -> list[CalendarEvent]:
    """Convert device logs into CalendarEvent objects.

    Pairs irrigation_start with the next irrigation_end/stop/cancel
    for the same zone. Skips and errors become short point-in-time events.
    Event summaries include the device name for multi-device support.
    """
    # Logs arrive newest-first; reverse to process chronologically
    chronological = list(reversed(logs))

    events: list[CalendarEvent] = []
    # Track open watering sessions by zone_id
    open_starts: dict[str, dict] = {}

    for log in chronological:
        event_type = log.get("eventType", "")
        zone_id = log.get("zoneId", "")
        created_at = log.get("createdAt")
        if not created_at:
            continue

        dt = _parse_dt(created_at)
        body = log.get("body", "")
        title = log.get("title", "")

        if event_type == "irrigation_status::irrigation_start":
            # Open a new watering session for this zone
            open_starts[zone_id] = {
                "start": dt,
                "body": body,
                "title": title,
                "zone_name": _extract_zone_name(body, "") or zone_id,
            }

        elif event_type in (
            "irrigation_status::irrigation_end",
            "irrigation_status::irrigation_manual_stop",
            "irrigation_status::irrigation_manual_cancel",
        ):
            # Close the matching open session
            start_info = open_starts.pop(zone_id, None)
            if start_info:
                zone_name = start_info["zone_name"]
                summary = f"{device_name}: Watered {zone_name}"
                if "manual_stop" in event_type:
                    summary = f"{device_name}: Watered {zone_name} (manually stopped)"
                elif "manual_cancel" in event_type:
                    summary = f"{device_name}: Watered {zone_name} (cancelled)"

                events.append(CalendarEvent(
                    start=start_info["start"],
                    end=dt,
                    summary=summary,
                    description=f"{start_info['body']}\n{body}".strip(),
                ))
            else:
                # End without a matching start - create a point event
                events.append(CalendarEvent(
                    start=dt,
                    end=dt + timedelta(minutes=1),
                    summary=title,
                    description=body,
                ))

        elif "weather_skip" in event_type:
            zone_name = _extract_zone_name(body, "") or zone_id
            events.append(CalendarEvent(
                start=dt,
                end=dt + timedelta(minutes=1),
                summary=f"{device_name}: Skipped {zone_name} (rain)",
                description=body,
            ))

        elif "irrigation_error" in event_type:
            events.append(CalendarEvent(
                start=dt,
                end=dt + timedelta(minutes=1),
                summary=f"{device_name}: {title}",
                description=body,
            ))

    # Close any remaining open sessions (watering may still be in progress)
    for zone_id, start_info in open_starts.items():
        zone_name = start_info["zone_name"]
        events.append(CalendarEvent(
            start=start_info["start"],
            end=start_info["start"] + timedelta(minutes=1),
            summary=f"{device_name}: Watering {zone_name} (in progress)",
            description=start_info["body"],
        ))

    return events


class OtOWateringCalendar(CoordinatorEntity, CalendarEntity):
    """Single calendar showing watering history for all OtO devices."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_names: dict[str, str],
    ) -> None:
        """Initialize the calendar entity."""
        super().__init__(coordinator)
        self._device_names = device_names
        self._attr_unique_id = "oto_watering_calendar"
        self._attr_name = "OtO Watering History"
        self._events: list[CalendarEvent] = []

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current or next upcoming event."""
        self._rebuild_events()
        if not self._events:
            return None
        now = datetime.now(timezone.utc)
        # Find current event (in progress)
        for ev in reversed(self._events):
            if ev.start <= now < ev.end:
                return ev
        # Return the most recent past event for display
        if self._events:
            return self._events[-1]
        return None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        self._rebuild_events()
        return [
            ev for ev in self._events
            if ev.end > start_date and ev.start < end_date
        ]

    def _rebuild_events(self) -> None:
        """Rebuild calendar events from coordinator log data for all devices."""
        if not self.coordinator.data:
            self._events = []
            return
        all_events: list[CalendarEvent] = []
        for device_id, device_name in self._device_names.items():
            logs = self.coordinator.data.get(device_id, [])
            all_events.extend(_build_calendar_events(logs, device_name))
        # Sort chronologically
        all_events.sort(key=lambda e: e.start)
        self._events = all_events
