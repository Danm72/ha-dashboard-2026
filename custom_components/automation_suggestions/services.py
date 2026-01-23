"""Service handlers for the Automation Suggestions integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN
from .coordinator import AutomationSuggestionsCoordinator

_LOGGER = logging.getLogger(__name__)

# Service names
SERVICE_ANALYZE_NOW = "analyze_now"
SERVICE_DISMISS = "dismiss"

# Service attribute names
ATTR_SUGGESTION_ID = "suggestion_id"

# Service schemas
SERVICE_DISMISS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_SUGGESTION_ID): cv.string,
    }
)


def _get_coordinator(hass: HomeAssistant) -> AutomationSuggestionsCoordinator:
    """Get the coordinator from config entries.

    Args:
        hass: Home Assistant instance.

    Returns:
        The AutomationSuggestionsCoordinator instance.

    Raises:
        HomeAssistantError: If no coordinator is found.
    """
    # Get config entries for this domain
    entries: list[ConfigEntry] = hass.config_entries.async_entries(DOMAIN)

    if not entries:
        raise HomeAssistantError(
            f"Integration {DOMAIN} is not set up"
        )

    # Get the first (and typically only) coordinator from runtime_data
    for entry in entries:
        if hasattr(entry, "runtime_data") and entry.runtime_data is not None:
            return entry.runtime_data

    raise HomeAssistantError(
        f"No coordinator found for {DOMAIN}. Is the integration configured?"
    )


async def async_handle_analyze_now(call: ServiceCall) -> None:
    """Handle the analyze_now service call.

    Triggers an immediate pattern analysis refresh.

    Args:
        call: Service call data.
    """
    _LOGGER.debug("Service call: analyze_now")
    hass = call.hass
    coordinator = _get_coordinator(hass)
    await coordinator.async_request_refresh()
    _LOGGER.info("Pattern analysis triggered via service call")


async def async_handle_dismiss(call: ServiceCall) -> None:
    """Handle the dismiss service call.

    Permanently hides a suggestion by adding it to the dismissed list.

    Args:
        call: Service call data containing suggestion_id.
    """
    suggestion_id = call.data[ATTR_SUGGESTION_ID]
    _LOGGER.debug("Service call: dismiss suggestion_id=%s", suggestion_id)

    if not suggestion_id:
        raise HomeAssistantError("suggestion_id is required")

    hass = call.hass
    coordinator = _get_coordinator(hass)
    await coordinator.async_dismiss(suggestion_id)
    _LOGGER.info("Suggestion %s dismissed via service call", suggestion_id)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for the Automation Suggestions integration.

    Args:
        hass: Home Assistant instance.
    """
    # Only register services once (handles multiple config entries)
    if hass.services.has_service(DOMAIN, SERVICE_ANALYZE_NOW):
        _LOGGER.debug("Services already registered, skipping")
        return

    hass.services.async_register(
        DOMAIN,
        SERVICE_ANALYZE_NOW,
        async_handle_analyze_now,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_DISMISS,
        async_handle_dismiss,
        schema=SERVICE_DISMISS_SCHEMA,
    )

    _LOGGER.debug("Registered services: %s, %s", SERVICE_ANALYZE_NOW, SERVICE_DISMISS)


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload services when the last entry is unloaded.

    Args:
        hass: Home Assistant instance.
    """
    # Only unload services if no entries remain
    entries = hass.config_entries.async_entries(DOMAIN)
    if entries:
        _LOGGER.debug("Other entries remain, keeping services registered")
        return

    hass.services.async_remove(DOMAIN, SERVICE_ANALYZE_NOW)
    hass.services.async_remove(DOMAIN, SERVICE_DISMISS)

    _LOGGER.debug("Unregistered services: %s, %s", SERVICE_ANALYZE_NOW, SERVICE_DISMISS)
