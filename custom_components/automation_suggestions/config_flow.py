"""Config flow for Automation Suggestions integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlowWithConfigEntry,
)
from homeassistant.core import callback

# ConfigFlowResult was added in HA 2024.1, fall back to FlowResult for older versions
try:
    from homeassistant.config_entries import ConfigFlowResult
except ImportError:
    from homeassistant.data_entry_flow import FlowResult as ConfigFlowResult
from .const import (
    CONF_ANALYSIS_INTERVAL,
    CONF_CONSISTENCY_THRESHOLD,
    CONF_DOMAIN_FILTER_MODE,
    CONF_FILTERED_DOMAINS,
    CONF_FILTERED_USERS,
    CONF_LOOKBACK_DAYS,
    CONF_MIN_OCCURRENCES,
    CONF_USER_FILTER_MODE,
    DEFAULT_ANALYSIS_INTERVAL,
    DEFAULT_CONSISTENCY_THRESHOLD,
    DEFAULT_DOMAIN_FILTER_MODE,
    DEFAULT_FILTERED_DOMAINS,
    DEFAULT_FILTERED_USERS,
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_MIN_OCCURRENCES,
    DEFAULT_USER_FILTER_MODE,
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
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=30)),
            vol.Required(
                CONF_LOOKBACK_DAYS,
                default=defaults.get(CONF_LOOKBACK_DAYS, DEFAULT_LOOKBACK_DAYS),
            ): vol.All(vol.Coerce(int), vol.Range(min=7, max=60)),
            vol.Required(
                CONF_MIN_OCCURRENCES,
                default=defaults.get(CONF_MIN_OCCURRENCES, DEFAULT_MIN_OCCURRENCES),
            ): vol.All(vol.Coerce(int), vol.Range(min=2, max=20)),
            vol.Required(
                CONF_CONSISTENCY_THRESHOLD,
                default=defaults.get(CONF_CONSISTENCY_THRESHOLD, DEFAULT_CONSISTENCY_THRESHOLD),
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                CONF_USER_FILTER_MODE,
                default=defaults.get(CONF_USER_FILTER_MODE, DEFAULT_USER_FILTER_MODE),
            ): vol.In(["none", "exclude", "include"]),
            vol.Optional(
                CONF_FILTERED_USERS,
                default=",".join(defaults.get(CONF_FILTERED_USERS, DEFAULT_FILTERED_USERS)),
            ): str,
            vol.Optional(
                CONF_DOMAIN_FILTER_MODE,
                default=defaults.get(CONF_DOMAIN_FILTER_MODE, DEFAULT_DOMAIN_FILTER_MODE),
            ): vol.In(["none", "exclude", "include"]),
            vol.Optional(
                CONF_FILTERED_DOMAINS,
                default=",".join(defaults.get(CONF_FILTERED_DOMAINS, DEFAULT_FILTERED_DOMAINS)),
            ): str,
        }
    )


class AutomationSuggestionsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Automation Suggestions."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        # Only allow single instance
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            # Parse comma-separated filter lists
            filtered_users = [
                u.strip() for u in user_input.get(CONF_FILTERED_USERS, "").split(",") if u.strip()
            ]
            filtered_domains = [
                d.strip().lower()
                for d in user_input.get(CONF_FILTERED_DOMAINS, "").split(",")
                if d.strip()
            ]

            return self.async_create_entry(
                title="Automation Suggestions",
                data={
                    CONF_ANALYSIS_INTERVAL: int(user_input[CONF_ANALYSIS_INTERVAL]),
                    CONF_LOOKBACK_DAYS: int(user_input[CONF_LOOKBACK_DAYS]),
                    CONF_MIN_OCCURRENCES: int(user_input[CONF_MIN_OCCURRENCES]),
                    CONF_CONSISTENCY_THRESHOLD: float(user_input[CONF_CONSISTENCY_THRESHOLD]),
                    CONF_USER_FILTER_MODE: user_input.get(
                        CONF_USER_FILTER_MODE, DEFAULT_USER_FILTER_MODE
                    ),
                    CONF_FILTERED_USERS: filtered_users,
                    CONF_DOMAIN_FILTER_MODE: user_input.get(
                        CONF_DOMAIN_FILTER_MODE, DEFAULT_DOMAIN_FILTER_MODE
                    ),
                    CONF_FILTERED_DOMAINS: filtered_domains,
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


class AutomationSuggestionsOptionsFlow(OptionsFlowWithConfigEntry):
    """Handle options flow for Automation Suggestions."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            # Parse comma-separated filter lists
            filtered_users = [
                u.strip() for u in user_input.get(CONF_FILTERED_USERS, "").split(",") if u.strip()
            ]
            filtered_domains = [
                d.strip().lower()
                for d in user_input.get(CONF_FILTERED_DOMAINS, "").split(",")
                if d.strip()
            ]

            return self.async_create_entry(
                title="",
                data={
                    CONF_ANALYSIS_INTERVAL: int(user_input[CONF_ANALYSIS_INTERVAL]),
                    CONF_LOOKBACK_DAYS: int(user_input[CONF_LOOKBACK_DAYS]),
                    CONF_MIN_OCCURRENCES: int(user_input[CONF_MIN_OCCURRENCES]),
                    CONF_CONSISTENCY_THRESHOLD: float(user_input[CONF_CONSISTENCY_THRESHOLD]),
                    CONF_USER_FILTER_MODE: user_input.get(
                        CONF_USER_FILTER_MODE, DEFAULT_USER_FILTER_MODE
                    ),
                    CONF_FILTERED_USERS: filtered_users,
                    CONF_DOMAIN_FILTER_MODE: user_input.get(
                        CONF_DOMAIN_FILTER_MODE, DEFAULT_DOMAIN_FILTER_MODE
                    ),
                    CONF_FILTERED_DOMAINS: filtered_domains,
                },
            )

        # Use current options or fall back to data
        current_options = {**self.config_entry.data, **self.config_entry.options}

        return self.async_show_form(
            step_id="init",
            data_schema=get_config_schema(current_options),
        )
