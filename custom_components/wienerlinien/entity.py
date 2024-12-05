"""Entity classes for Vienna Lines integration."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from .const import DOMAIN

# Pure Data Models
@dataclass
class Coordinates:
    """Coordinates of a stop."""
    longitude: float
    latitude: float

    @classmethod
    def from_dict(cls, data: list[float]) -> Coordinates:
        """Create coordinates from API response."""
        return cls(longitude=data[0], latitude=data[1])

@dataclass
class StopLocation:
    """Location information for a stop."""
    name: str
    title: str
    municipality: str
    rbl: int  # Stop ID
    coordinates: Coordinates

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StopLocation:
        """Create stop location from API response."""
        properties = data["properties"]
        return cls(
            name=properties["name"],
            title=properties["title"],
            municipality=properties["municipality"],
            rbl=properties["attributes"]["rbl"],
            coordinates=Coordinates.from_dict(data["geometry"]["coordinates"])
        )

@dataclass
class DepartureTime:
    """Departure time information."""
    time_planned: datetime
    time_real: Optional[datetime]
    countdown: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DepartureTime:
        """Create departure time from API response."""
        return cls(
            time_planned=datetime.fromisoformat(data["timePlanned"]),
            time_real=datetime.fromisoformat(data["timeReal"]) if "timeReal" in data else None,
            countdown=data["countdown"]
        )

@dataclass
class Vehicle:
    """Vehicle information."""
    name: str
    towards: str
    direction: str
    platform: str
    barrier_free: bool
    line_id: int
    vehicle_type: str
    realtime_supported: bool
    traffic_jam: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Vehicle:
        """Create vehicle from API response."""
        return cls(
            name=data["name"],
            towards=data["towards"],
            direction=data["direction"],
            platform=data["platform"],
            barrier_free=data["barrierFree"],
            line_id=data["linienId"],
            vehicle_type=data["type"],
            realtime_supported=data["realtimeSupported"],
            traffic_jam=data["trafficjam"]
        )

@dataclass
class Line:
    """Line information."""
    name: str
    towards: str
    direction: str
    platform: str
    barrier_free: bool
    line_id: int
    line_type: str
    departures: list[Departure]

    @classmethod
    def from_dict(cls, data: dict[str, Any], monitor: Monitor) -> Line:
        """Create line from API response."""
        departures_data = data.get("departures", {}).get("departure", [])
        line = cls(
            name=data["name"],
            towards=data["towards"],
            direction=data["direction"],
            platform=data["platform"],
            barrier_free=data["barrierFree"],
            line_id=data["lineId"],
            line_type=data["type"],
            departures=[]  # Initialize empty, will be filled after creation
        )
        # Create departures after line object exists
        line.departures = [Departure.from_dict(d, monitor) for d in departures_data]
        return line

# Home Assistant Entities
class Monitor:
    """Monitor information for a stop."""

    def __init__(self, location: StopLocation, lines: list[Line]) -> None:
        """Initialize the monitor."""
        self.location = location
        self.lines = lines
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, f"wienerlinien_stop_{location.rbl}")},
            name=f"Wiener Linien {location.title}",
            manufacturer="Wiener Linien",
            model="Public Transport Stop",
            sw_version="1.0",
            configuration_url=f"https://www.wienerlinien.at/ogd_realtime/monitor?rbl={location.rbl}",
        )

    @property
    def available_lines(self) -> list[str]:
        """Return list of available lines at this stop."""
        return [line.name for line in self.lines]

    @property
    def next_departures(self) -> list[tuple[str, datetime]]:
        """Return list of next departures for all lines."""
        departures = []
        for line in self.lines:
            if line.departures:
                next_dep = line.departures[0]
                departures.append((
                    f"{line.name} to {line.towards}",
                    next_dep.departure_time.time_real or next_dep.departure_time.time_planned
                ))
        return sorted(departures, key=lambda x: x[1])

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Monitor":
        """Create monitor from API response."""
        monitor = cls(
            location=StopLocation.from_dict(data["locationStop"]),
            lines=[]  # Initialize empty
        )
        # Create lines after monitor exists
        monitor.lines = [Line.from_dict(l, monitor) for l in data["lines"]]
        return monitor


class Departure(SensorEntity):
    """Departure information sensor."""
    
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_has_entity_name = True
    
    def __init__(self, departure_time: DepartureTime, vehicle: Vehicle, monitor: Monitor) -> None:
        """Initialize departure sensor."""
        self.departure_time = departure_time
        self.vehicle = vehicle
        self.monitor = monitor
        
        self._attr_unique_id = f"departure_{monitor.location.rbl}_{vehicle.line_id}_{vehicle.direction}"
        self._attr_name = f"{vehicle.name} to {vehicle.towards}"
        self._attr_device_info = monitor.device_info

    @property
    def native_value(self) -> datetime:
        """Return the actual departure time."""
        return self.departure_time.time_real or self.departure_time.time_planned

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attrs = {
            "planned_departure": self.departure_time.time_planned,
            "real_departure": self.departure_time.time_real,
            "countdown": self.departure_time.countdown,
            "line": self.vehicle.name,
            "destination": self.vehicle.towards,
            "direction": self.vehicle.direction,
            "platform": self.vehicle.platform,
            "barrier_free": self.vehicle.barrier_free,
            "vehicle_type": self.vehicle.vehicle_type,
            "stop_name": self.monitor.location.title,
            "municipality": self.monitor.location.municipality,
        }
        
        if self.monitor.location.coordinates:
            attrs.update({
                ATTR_LATITUDE: self.monitor.location.coordinates.latitude,
                ATTR_LONGITUDE: self.monitor.location.coordinates.longitude,
            })
        
        return attrs

    @classmethod
    def from_dict(cls, data: dict[str, Any], monitor: Monitor) -> "Departure":
        """Create departure from API response."""
        departure_time = DepartureTime.from_dict(data["departureTime"])
        vehicle = Vehicle.from_dict(data["vehicle"])
        
        return cls(
            departure_time=departure_time,
            vehicle=vehicle,
            monitor=monitor
        )