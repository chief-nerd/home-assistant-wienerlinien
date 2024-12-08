"""Entity classes for Vienna Lines integration."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
import logging

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


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
    def from_dict(cls, data: dict[str, Any], location_data: dict[str, Any] | None = None) -> Vehicle:
        """Create vehicle from API response."""
        # Handle both linienId and lineId
        line_id = data.get("linienId", data.get("lineId"))
        if line_id is None:
            _LOGGER.error("No line ID found in data: %s", data)
            raise ValueError("Missing line ID")
            
        return cls(
            name=data["name"],
            towards=data["towards"],
            direction=data["direction"],
            platform=data["platform"],
            barrier_free=data["barrierFree"],
            line_id=line_id,
            vehicle_type=data["type"],
            realtime_supported=data.get("realtimeSupported", False),
            traffic_jam=data.get("trafficjam", False)
        )

@dataclass
class Departure:
    """Departure information."""
    departure_time: DepartureTime
    vehicle: Vehicle

    @classmethod
    def from_dict(cls, data: dict[str, Any], vehicle_info: Vehicle | None = None) -> "Departure":
        """Create departure from API response.
        
        For metro lines, one vehicle can have multiple departure times.
        The vehicle info is passed separately in these cases.
        """
        departure_time = DepartureTime.from_dict(data["departureTime"])
        
        # Use provided vehicle info or parse from data
        vehicle = vehicle_info or Vehicle.from_dict(data["vehicle"])
            
        return cls(
            departure_time=departure_time,
            vehicle=vehicle
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
    gate: str | None
    departures: list[Departure]

    @classmethod
    def from_dict(cls, data: dict[str, Any], location_data: dict[str, Any] | None = None) -> Line:
        """Create line from API response."""
        gate = None
        if isinstance(location_data, dict):
            gate = location_data.get("properties", {}).get("gate")
            
        departures_data = data.get("departures", {}).get("departure", [])
        departures = []
        
        # For metro lines, use same vehicle info for all departure times
        if data.get("type") == "ptMetro" and departures_data:
            vehicle = Vehicle.from_dict(data)
            departures = [
                Departure.from_dict(dep_data, vehicle) 
                for dep_data in departures_data
            ]
        else:
            departures = [
                Departure.from_dict(dep_data)
                for dep_data in departures_data
            ]
                
        return cls(
            name=data["name"],
            towards=data["towards"],
            direction=data["direction"],
            platform=data["platform"],
            barrier_free=data["barrierFree"],
            line_id=data["lineId"],
            line_type=data["type"],
            gate=gate,
            departures=departures
        )

# Home Assistant Entities
class Monitor:
    """Monitor information for a stop."""

    def __init__(self, location: StopLocation, lines: list[Line]) -> None:
        """Initialize the monitor."""
        self.location = location
        self.lines = lines
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, f"wienerlinien_stop_{location.rbl}")},
            name=f"{location.title} - {self.create_name()}",
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
    
    def create_name(self) -> str:
        """Create a name for this entity."""
        line_names: str = ", ".join(self.available_lines)
        for line in self.lines:
            if line.departures:
                return f"{line_names} towards {line.towards}"
    

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Monitor":
        """Create monitor from API response."""
        location = StopLocation.from_dict(data["locationStop"])
        lines = [Line.from_dict(l, data.get("locationStop")) for l in data["lines"]]
        return cls(location=location, lines=lines)
