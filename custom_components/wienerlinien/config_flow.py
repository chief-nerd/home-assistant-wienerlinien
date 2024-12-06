"""Config flow for Vienna Lines integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
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

class WienerLinienConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            stops = user_input[CONF_STOPS].split(",")
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