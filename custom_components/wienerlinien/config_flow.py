"""Config flow for Vienna Lines integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_STOPS, DOMAIN, DEFAULT_DEPARTURE_LIMIT

_LOGGER = logging.getLogger(__name__)

class WienerLinienConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            stops = user_input[CONF_STOPS].split(",")
            # Create friendly title from stop names
            title = "Wiener Linien Public Transport"
            return self.async_create_entry(
                title=title,
                data={
                    CONF_STOPS: user_input[CONF_STOPS],
                    "departure_limit": user_input.get("departure_limit", DEFAULT_DEPARTURE_LIMIT)
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
            }),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
