"""The Wiener Linien integration."""
import asyncio
from datetime import timedelta
import logging
from typing import Any

import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from datetime import datetime, timedelta
import aiohttp
from .const import DOMAIN, BASE_URL
from .entity import Monitor

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Wiener Linien from a config entry."""
    stops = entry.data["stops"]
    session = async_create_clientsession(hass)
    api = WienerLinienAPI(session, stops)
    scan_interval = timedelta(seconds=entry.data.get("scan_interval", 30))


    async def async_update_data() -> list[Monitor]:
        """Fetch data from API."""
        try:
            async with async_timeout.timeout(10):
                data = await api.get_json()
                if not data:
                    raise UpdateFailed("No data received from API")
                
                # Debug raw monitor data
                _LOGGER.debug(
                    "Raw monitors data: %d monitors received",
                    len(data.get("data", {}).get("monitors", []))
                )
                for monitor in data.get("data", {}).get("monitors", []):
                    _LOGGER.debug(
                        "Monitor: location=%s, rbl=%s, lines=%d",
                        monitor.get("locationStop", {}).get("properties", {}).get("title"),
                        monitor.get("locationStop", {}).get("properties", {}).get("attributes", {}).get("rbl"),
                        len(monitor.get("lines", []))
                    )
                
                monitors = await parse_api_response(data)
                if not monitors:
                    raise UpdateFailed("No monitors found in API response")
                return monitors
        except Exception as ex:
            raise UpdateFailed(f"Error fetching data: {ex}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=scan_interval,
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        return False

    entry.async_on_unload(entry.add_update_listener(update_listener))
    entry.runtime_data = {
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry.runtime_data.clear()
    return unload_ok

async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)

class WienerLinienAPI:
    """Wiener Linien API client."""

    def __init__(self, session, stops: str) -> None:
        """Initialize the API client."""
        self.session = session
        self.stops = stops
        self._cache = {}
        self._cache_timeout = timedelta(seconds=30)
        self._retry_count = 3
        self._retry_delay = 1
        self._timeout = 10

    async def get_json(self) -> dict[str, Any] | None:
        """Get json from API endpoint with retry and caching."""
        try:
            # Check cache
            cache_key = self.stops
            if cache_key in self._cache:
                data, timestamp = self._cache[cache_key]
                if datetime.now() - timestamp < self._cache_timeout:
                    _LOGGER.debug("Using cached data from %s", timestamp)
                    return data
                else:
                    _LOGGER.debug("Cache expired, fetching new data")
            else:
                _LOGGER.debug("No cache found, fetching new data")

            stop_list = list(set(self.stops.split(",")))
            stop_query = "&rbl=".join(stop_list)
            url = f"{BASE_URL}?rbl={stop_query}&activateTrafficInfo=stoerunglang"
            
            for retry in range(self._retry_count):
                try:
                    async with async_timeout.timeout(self._timeout):
                        async with self.session.get(url) as response:
                            response.raise_for_status()
                            data = await response.json()
                            
                            # Process and merge monitors
                            processed_monitors = {}
                            monitors = data.get("data", {}).get("monitors", [])
                            
                            for monitor in monitors:
                                rbl = monitor.get("locationStop", {}).get("properties", {}).get("attributes", {}).get("rbl")
                                if not rbl:
                                    continue

                                lines = monitor.get("lines", [])
                                if not lines:
                                    continue

                                if rbl in processed_monitors:
                                    processed_monitors[rbl]["lines"].extend(lines)
                                else:
                                    processed_monitors[rbl] = {
                                        "locationStop": monitor["locationStop"],
                                        "lines": lines,
                                        "attributes": monitor.get("attributes", {})
                                    }

                            data["data"]["monitors"] = list(processed_monitors.values())
                            
                            # Update cache with timestamp
                            self._cache[cache_key] = (data, datetime.now())
                            _LOGGER.debug("Updated cache with new data")
                            return data

                except asyncio.TimeoutError:
                    delay = self._retry_delay * (2 ** retry)
                    _LOGGER.warning(
                        "Request timed out (attempt %d/%d), retrying in %d seconds",
                        retry + 1, 
                        self._retry_count,
                        delay
                    )
                    if retry < self._retry_count - 1:
                        await asyncio.sleep(delay)
                    continue
                except aiohttp.ClientError as err:
                    _LOGGER.error("Connection error: %s", err)
                    # Use cached data if available
                    if cache_key in self._cache:
                        data, timestamp = self._cache[cache_key]
                        _LOGGER.info("Using cached data due to connection error")
                        return data
                    break

        except Exception as ex:
            _LOGGER.error("Failed to fetch data: %s", ex)
            if cache_key in self._cache:
                data, timestamp = self._cache[cache_key]
                _LOGGER.info("Using cached data due to error")
                return data
        
        return None

async def parse_api_response(response: dict[str, Any]) -> list[Monitor]:
    """Parse API response into Monitor objects."""
    try:
        if "data" not in response or "monitors" not in response["data"]:
            _LOGGER.error("Invalid API response format")
            return []
            
        monitors_data = response["data"]["monitors"]
        _LOGGER.debug("Parsing %d monitors", len(monitors_data))
        
        # Create Monitor objects directly from data
        monitors = []
        for monitor_data in monitors_data:
            try:
                monitor = Monitor.from_dict(monitor_data)
                monitors.append(monitor)
                _LOGGER.debug(
                    "Parsed monitor: location=%s, rbl=%s, lines=%d",
                    monitor.location.title,
                    monitor.location.rbl,
                    len(monitor.lines)
                )
            except Exception as ex:
                _LOGGER.error(
                    "Failed to parse monitor: %s",
                    ex
                )
                
        return monitors
        
    except Exception as ex:
        _LOGGER.error("Failed to parse API response: %s", ex)
        return []