"""The Automation Suggestions integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import AutomationSuggestionsCoordinator
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor", "binary_sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Automation Suggestions from a config entry."""
    _LOGGER.debug("Setting up Automation Suggestions integration")

    hass.data.setdefault(DOMAIN, {})

    # Create the coordinator
    coordinator = AutomationSuggestionsCoordinator(hass, entry)

    # Load dismissed and notified suggestions from storage
    await coordinator.async_load_persisted()

    # Perform first refresh to populate data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator in hass.data
    hass.data[DOMAIN][entry.entry_id] = {"coordinator": coordinator}

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Set up services
    await async_setup_services(hass)

    # Forward entry setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Automation Suggestions integration")

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Remove data from hass.data
        hass.data[DOMAIN].pop(entry.entry_id)

        # Unload services (only if no entries remain)
        await async_unload_services(hass)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update.

    Called when the user updates options via the options flow.
    """
    _LOGGER.debug("Options updated, refreshing coordinator config")

    # Get the coordinator
    coordinator: AutomationSuggestionsCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    # Update coordinator configuration
    coordinator.update_config(entry)

    # Trigger a refresh with new settings
    await coordinator.async_request_refresh()
