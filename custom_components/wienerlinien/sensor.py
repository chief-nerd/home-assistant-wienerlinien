"""Support for Wiener Linien sensors."""
from __future__ import annotations
from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE


from .const import DOMAIN, ENTITY_PREFIX, TIME_STR_FORMAT, DEFAULT_DEPARTURE_LIMIT
from .entity import Line, Monitor

_LOGGER = logging.getLogger(__name__)

class LineEntity(CoordinatorEntity, SensorEntity):
    """Line information entity."""
    
    def __init__(self, coordinator, line: Line, monitor: Monitor, 
                 direction_text: str, direction: str, towards: str, 
                 unique_id_suffix: str, departure_limit: int) -> None:
        """Initialize the line entity."""
        super().__init__(coordinator)
        self.line = line
        self.monitor = monitor
        self.direction_text = direction_text
        self.direction = direction
        self.towards = towards
        self.departure_limit = departure_limit
        self._cached_departures = None
        
        self._attr_unique_id = (
            f"{ENTITY_PREFIX}line_{monitor.location.title}_{monitor.location.rbl}_"
            f"{line.line_id}_{direction}_{unique_id_suffix}"
        )
        self._attr_name = (
            f"{monitor.location.title} {line.name} {direction_text} "
            f"to {towards}"
        )
        self._attr_device_info = monitor.device_info
        self._attr_icon = self._get_icon()

    def _get_icon(self) -> str:
        """Get icon based on line type."""
        if self.line.line_type.lower() == "ptbus":
            return "mdi:bus"
        elif self.line.line_type.lower() == "pttram":
            return "mdi:tram"
        elif self.line.line_type.lower() == "ptmetro":
            return "mdi:subway-variant"
        return "mdi:train-variant"

    @property
    def _filtered_departures(self) -> list:
        """Get filtered and sorted departures for this direction and towards."""
        if self._cached_departures is None:
            for monitor in self.coordinator.data:
                if monitor.location.rbl == self.monitor.location.rbl:
                    for line in monitor.lines:
                        if line.line_id == self.line.line_id:
                            # Filter by both direction and towards
                            departures = [
                                dep for dep in line.departures 
                                if dep.vehicle.direction == self.direction
                                and dep.vehicle.towards == self.towards
                            ]
                            self._cached_departures = sorted(
                                departures,
                                key=lambda x: x.departure_time.time_planned
                            )
                            _LOGGER.debug(
                                "Found %d departures for line %s direction %s towards %s at stop %s",
                                len(departures),
                                line.name,
                                self.direction,
                                self.towards,
                                self.monitor.location.title
                            )
                            break
            if self._cached_departures is None:
                self._cached_departures = []
        return self._cached_departures

    def _async_update_data(self):
        """Clear cache when coordinator updates."""
        self._cached_departures = None
        return super()._async_update_data()

    @property
    def native_value(self) -> str | None:
        """Return time until departure in minutes."""
        departures = self._filtered_departures
        if departures:
            next_dep = departures[0]
            departure_time = next_dep.departure_time.time_real or next_dep.departure_time.time_planned
            now = datetime.now(departure_time.tzinfo)
            minutes = int((departure_time - now).total_seconds() / 60)
            
            if minutes < 0:
                return "Departed"
            elif minutes == 0:
                return "Now"
            else:
                return f"Arriving in {minutes} min"
        return None
    
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        _LOGGER.debug(
            "Entity %s added to hass, coordinator interval: %s",
            self._attr_unique_id,
            self.coordinator.update_interval
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug(
            "Coordinator update received for %s",
            self._attr_unique_id
        )
        self._cached_departures = None
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attrs = {
            "platform": self.line.platform,
            "barrier_free": self.line.barrier_free,
            "line_type": self.line.line_type,
            "municipality": self.monitor.location.municipality,
            ATTR_LATITUDE: self.monitor.location.coordinates.latitude,
            ATTR_LONGITUDE: self.monitor.location.coordinates.longitude,
            "departures": []
        }

        try:
            departures = self._filtered_departures[:self.departure_limit]
            attrs["departures"] = [
                {
                    "location": self.monitor.location.title,
                    "line_name": self.line.name,
                    "line_icon": self._get_icon(),
                    "towards": dep.vehicle.towards,
                    "planned_time": dep.departure_time.time_planned.strftime(TIME_STR_FORMAT),
                    "real_time": dep.departure_time.time_real.strftime(TIME_STR_FORMAT) if dep.departure_time.time_real else None,
                    "barrier_free": dep.vehicle.barrier_free,
                    "realtime_supported": dep.vehicle.realtime_supported,
                    "traffic_jam": dep.vehicle.traffic_jam
                }
                for dep in departures
            ]
        except Exception:
            pass
        return attrs

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Wiener Linien sensors based on a config entry."""
    coordinator = entry.runtime_data["coordinator"]
    departure_limit = entry.data.get("departure_limit", DEFAULT_DEPARTURE_LIMIT)
    
    entities = []
    
    # Track line/stop/direction combinations
    line_stop_directions = {}
    
    _LOGGER.debug("Processing %d monitors", len(coordinator.data))
    for monitor in coordinator.data:
        _LOGGER.debug(
            "Processing monitor data: location=%s, rbl=%s, lines=%d",
            monitor.location.title,
            monitor.location.rbl,
            len(monitor.lines)
        )
        
        for line in monitor.lines:
            _LOGGER.debug(
                "Processing line %s at RBL %s with %d departures",
                line.name,
                monitor.location.rbl,
                len(line.departures)
            )
            
            # Use RBL in key to handle same physical stop different directions
            key = (line.line_id, monitor.location.rbl)
            if key not in line_stop_directions:
                line_stop_directions[key] = {
                    'line': line,
                    'monitor': monitor,
                    'direction_data': {}
                }
            
            # Track each unique direction/towards combination
            for departure in line.departures:
                direction_key = (departure.vehicle.direction, departure.vehicle.towards)
                if direction_key not in line_stop_directions[key]['direction_data']:
                    _LOGGER.debug(
                        "Found new direction for line %s at RBL %s: %s towards %s",
                        line.name,
                        monitor.location.rbl,
                        departure.vehicle.direction,
                        departure.vehicle.towards
                    )
                    line_stop_directions[key]['direction_data'][direction_key] = {
                        'direction': departure.vehicle.direction,
                        'towards': departure.vehicle.towards
                    }

    # Create entities for each unique combination
    for (line_id, rbl), data in line_stop_directions.items():
        for (direction, towards), direction_data in data['direction_data'].items():
            direction_text = "Outbound" if direction == "H" else "Inbound"
            safe_towards = towards.replace(",", "").replace(" ", "_").lower()
            
            _LOGGER.debug(
                "Creating entity for line %s at %s (RBL: %s): direction %s towards %s",
                data['line'].name,
                data['monitor'].location.title,
                rbl,
                direction,
                towards
            )
            
            entities.append(
                LineEntity(
                    coordinator=coordinator,
                    line=data['line'],
                    monitor=data['monitor'],
                    direction_text=direction_text,
                    direction=direction,
                    towards=towards,
                    unique_id_suffix=safe_towards,
                    departure_limit=departure_limit
                )
            )

    _LOGGER.debug("Created %d total entities", len(entities))
    async_add_entities(entities)