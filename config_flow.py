"""Config flow for Solar Savings integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_CURRENCY_SYMBOL,
    CONF_ELECTRICITY_RATE,
    CONF_SETUP_COST,
    CONF_SOLAR_ENERGY_MONTH,
    CONF_SOLAR_ENERGY_TODAY,
    CONF_SOLAR_POWER_SENSOR,
    DEFAULT_CURRENCY_SYMBOL,
    DEFAULT_ELECTRICITY_RATE,
    DEFAULT_SETUP_COST,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _build_schema(defaults: dict | None = None) -> vol.Schema:
    """Build the config schema with optional defaults."""
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_SOLAR_POWER_SENSOR,
                default=d.get(CONF_SOLAR_POWER_SENSOR, ""),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(
                CONF_SOLAR_ENERGY_TODAY,
                default=d.get(CONF_SOLAR_ENERGY_TODAY, ""),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(
                CONF_SOLAR_ENERGY_MONTH,
                default=d.get(CONF_SOLAR_ENERGY_MONTH, ""),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(
                CONF_ELECTRICITY_RATE,
                default=d.get(CONF_ELECTRICITY_RATE, DEFAULT_ELECTRICITY_RATE),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.01,
                    max=5.0,
                    step=0.01,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_SETUP_COST,
                default=d.get(CONF_SETUP_COST, DEFAULT_SETUP_COST),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=100000,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_CURRENCY_SYMBOL,
                default=d.get(CONF_CURRENCY_SYMBOL, DEFAULT_CURRENCY_SYMBOL),
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
        }
    )


class SolarSavingsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solar Savings."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate that the sensors exist
            for key in (
                CONF_SOLAR_POWER_SENSOR,
                CONF_SOLAR_ENERGY_TODAY,
                CONF_SOLAR_ENERGY_MONTH,
            ):
                entity_id = user_input.get(key)
                if entity_id and not self.hass.states.get(entity_id):
                    errors[key] = "entity_not_found"

            if not errors:
                return self.async_create_entry(
                    title="Solar Savings",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Get the options flow."""
        return SolarSavingsOptionsFlow(config_entry)


class SolarSavingsOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Solar Savings."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            for key in (
                CONF_SOLAR_POWER_SENSOR,
                CONF_SOLAR_ENERGY_TODAY,
                CONF_SOLAR_ENERGY_MONTH,
            ):
                entity_id = user_input.get(key)
                if entity_id and not self.hass.states.get(entity_id):
                    errors[key] = "entity_not_found"

            if not errors:
                return self.async_create_entry(title="", data=user_input)

        # Merge current data + options as defaults
        defaults = {**self.config_entry.data, **self.config_entry.options}

        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(defaults),
            errors=errors,
        )
