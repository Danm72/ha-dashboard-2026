"""Binary sensor platform for the Automation Suggestions integration.

Provides a binary sensor indicating whether automation suggestions are available.
"""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AutomationSuggestionsCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Automation Suggestions binary sensors from a config entry.

    Args:
        hass: Home Assistant instance.
        entry: Config entry being set up.
        async_add_entities: Callback to add entities.
    """
    coordinator: AutomationSuggestionsCoordinator = entry.runtime_data

    entities: list[BinarySensorEntity] = [
        AutomationSuggestionsAvailableBinarySensor(coordinator, entry),
    ]

    async_add_entities(entities)
    _LOGGER.debug("Added %d automation suggestion binary sensors", len(entities))


class AutomationSuggestionsAvailableBinarySensor(
    CoordinatorEntity[AutomationSuggestionsCoordinator], BinarySensorEntity
):
    """Binary sensor indicating whether automation suggestions are available."""

    _attr_has_entity_name = True
    _attr_translation_key = "available"

    def __init__(
        self,
        coordinator: AutomationSuggestionsCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the available binary sensor.

        Args:
            coordinator: The data update coordinator.
            entry: Config entry for unique ID generation.
        """
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_available"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Automation Suggestions",
            manufacturer="Home Assistant Community",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def is_on(self) -> bool:
        """Return True if there are suggestions available."""
        if self.coordinator.data is None:
            return False
        return len(self.coordinator.data) > 0

    @property
    def icon(self) -> str:
        """Return the icon based on whether suggestions are available."""
        if self.is_on:
            return "mdi:bell-ring-outline"
        return "mdi:bell-outline"
