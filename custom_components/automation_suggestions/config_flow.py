"""Config flow for Automation Suggestions integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_ANALYSIS_INTERVAL,
    CONF_CONSISTENCY_THRESHOLD,
    CONF_LOOKBACK_DAYS,
    CONF_MIN_OCCURRENCES,
    DEFAULT_ANALYSIS_INTERVAL,
    DEFAULT_CONSISTENCY_THRESHOLD,
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_MIN_OCCURRENCES,
    DOMAIN,
)


def get_config_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Get the config schema with optional defaults."""
    if defaults is None:
        defaults = {}

    return vol.Schema(
        {
            vol.Required(
                CONF_ANALYSIS_INTERVAL,
                default=defaults.get(CONF_ANALYSIS_INTERVAL, DEFAULT_ANALYSIS_INTERVAL),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=30,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                ),
            ),
            vol.Required(
                CONF_LOOKBACK_DAYS,
                default=defaults.get(CONF_LOOKBACK_DAYS, DEFAULT_LOOKBACK_DAYS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=7,
                    max=60,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                ),
            ),
            vol.Required(
                CONF_MIN_OCCURRENCES,
                default=defaults.get(CONF_MIN_OCCURRENCES, DEFAULT_MIN_OCCURRENCES),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=2,
                    max=20,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                ),
            ),
            vol.Required(
                CONF_CONSISTENCY_THRESHOLD,
                default=defaults.get(
                    CONF_CONSISTENCY_THRESHOLD, DEFAULT_CONSISTENCY_THRESHOLD
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.5,
                    max=1.0,
                    step=0.05,
                    mode=selector.NumberSelectorMode.SLIDER,
                ),
            ),
        }
    )


class AutomationSuggestionsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Automation Suggestions."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        # Only allow single instance
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            # Convert float values from selectors to proper types
            return self.async_create_entry(
                title="Automation Suggestions",
                data={
                    CONF_ANALYSIS_INTERVAL: int(user_input[CONF_ANALYSIS_INTERVAL]),
                    CONF_LOOKBACK_DAYS: int(user_input[CONF_LOOKBACK_DAYS]),
                    CONF_MIN_OCCURRENCES: int(user_input[CONF_MIN_OCCURRENCES]),
                    CONF_CONSISTENCY_THRESHOLD: float(
                        user_input[CONF_CONSISTENCY_THRESHOLD]
                    ),
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=get_config_schema(),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> AutomationSuggestionsOptionsFlow:
        """Create the options flow."""
        return AutomationSuggestionsOptionsFlow(config_entry)


class AutomationSuggestionsOptionsFlow(OptionsFlow):
    """Handle options flow for Automation Suggestions."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_ANALYSIS_INTERVAL: int(user_input[CONF_ANALYSIS_INTERVAL]),
                    CONF_LOOKBACK_DAYS: int(user_input[CONF_LOOKBACK_DAYS]),
                    CONF_MIN_OCCURRENCES: int(user_input[CONF_MIN_OCCURRENCES]),
                    CONF_CONSISTENCY_THRESHOLD: float(
                        user_input[CONF_CONSISTENCY_THRESHOLD]
                    ),
                },
            )

        # Use current options or fall back to data
        current_options = {**self.config_entry.data, **self.config_entry.options}

        return self.async_show_form(
            step_id="init",
            data_schema=get_config_schema(current_options),
        )
