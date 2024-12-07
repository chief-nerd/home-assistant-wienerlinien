from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.helpers import entity_registry as er
from homeassistant.components.sensor import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DEFAULT_DEPARTURE_LIMIT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    MAX_SCAN_INTERVAL,
    CONF_STOPS,
)
_LOGGER = logging.getLogger(__name__)

class WienerLinienConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            title = "Wiener Linien Public Transport"
            return self.async_create_entry(
                title=title,
                data={
                    CONF_STOPS: user_input[CONF_STOPS],
                    "departure_limit": user_input.get("departure_limit", DEFAULT_DEPARTURE_LIMIT),
                    "scan_interval": user_input.get("scan_interval", DEFAULT_SCAN_INTERVAL)
                }
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_STOPS): str,
                vol.Optional(
                    "departure_limit", 
                    default=DEFAULT_DEPARTURE_LIMIT
                ): vol.All(
                    vol.Coerce(int), 
                    vol.Range(min=1, max=10)
                ),
                vol.Optional(
                    "scan_interval",
                    default=DEFAULT_SCAN_INTERVAL
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
                ),
            }),
            errors=errors,
        )
    
    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return WienerLinienOptionsFlow(config_entry)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle reconfiguration."""
        errors = {}

        # Get the entry in a safe way
        try:
            entry = self._get_reconfigure_entry()
        except ValueError:
            return self.async_abort(reason="entry_not_found")
        
        if user_input is not None:
            try:
                # Get old and new stops for comparison
                old_stops = set(int(s.strip()) for s in entry.data[CONF_STOPS].split(","))
                new_stops = set(int(s.strip()) for s in user_input[CONF_STOPS].split(","))
                
                if not new_stops:
                    errors["base"] = "invalid_stops"
            except ValueError:
                errors["base"] = "invalid_stops"

            if not errors:
                # Find removed stops
                removed_stops = old_stops - new_stops
                
                if removed_stops:
                    # Get entity registry
                    ent_reg = er.async_get(self.hass)
                    
                    # Create list of entities to remove first
                    entities_to_remove = [
                        entity.entity_id
                        for entity in list(ent_reg.entities.values())
                        if (entity.config_entry_id == entry.entry_id and
                            any(f"_{stop}_" in entity.unique_id for stop in removed_stops))
                    ]
                    
                    # Remove entities
                    for entity_id in entities_to_remove:
                        ent_reg.async_remove(entity_id)

                # Update entry with new data
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        CONF_STOPS: user_input[CONF_STOPS],
                        "departure_limit": user_input.get("departure_limit", DEFAULT_DEPARTURE_LIMIT),
                        "scan_interval": user_input.get("scan_interval", DEFAULT_SCAN_INTERVAL)
                    }
                )
                
                # Reload entry to create new entities
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")

        # Return form
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({
                vol.Required(CONF_STOPS, default=entry.data[CONF_STOPS]): str,
                vol.Optional(
                    "departure_limit", 
                    default=entry.data.get("departure_limit", DEFAULT_DEPARTURE_LIMIT)
                ): vol.All(
                    vol.Coerce(int), 
                    vol.Range(min=1, max=10)
                ),
                vol.Optional(
                    "scan_interval",
                    default=entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
                ),
            }),
            errors=errors,
        )

class WienerLinienOptionsFlow(OptionsFlow):
    """Handle options."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.current_options = entry.options
        self.current_data = entry.data

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    "departure_limit": user_input["departure_limit"],
                    "scan_interval": user_input["scan_interval"]
                }
            )

        options = {
            vol.Optional(
                "departure_limit",
                default=self.current_options.get(
                    "departure_limit", 
                    self.current_data["departure_limit"]
                )
            ): vol.All(
                vol.Coerce(int),
                vol.Range(min=1, max=10)
            ),
            vol.Optional(
                "scan_interval",
                default=self.current_options.get(
                    "scan_interval", 
                    self.current_data["scan_interval"]
                )
            ): vol.All(
                vol.Coerce(int),
                vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
            ),
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(options)
        )