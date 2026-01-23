"""Sensor platform for the Automation Suggestions integration.

Provides sensors to expose automation suggestion data to Home Assistant.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AutomationSuggestionsCoordinator

if TYPE_CHECKING:
    from .analyzer import Suggestion

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Automation Suggestions sensors from a config entry.

    Args:
        hass: Home Assistant instance.
        entry: Config entry being set up.
        async_add_entities: Callback to add entities.
    """
    coordinator: AutomationSuggestionsCoordinator = entry.runtime_data

    entities: list[SensorEntity] = [
        AutomationSuggestionsCountSensor(coordinator, entry),
        AutomationSuggestionsTopSensor(coordinator, entry),
        AutomationSuggestionsLastAnalysisSensor(coordinator, entry),
    ]

    async_add_entities(entities)
    _LOGGER.debug("Added %d automation suggestion sensors", len(entities))


class AutomationSuggestionsBaseSensor(
    CoordinatorEntity[AutomationSuggestionsCoordinator], SensorEntity
):
    """Base class for automation suggestion sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AutomationSuggestionsCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the base sensor.

        Args:
            coordinator: The data update coordinator.
            entry: Config entry for unique ID generation.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Automation Suggestions",
            manufacturer="Home Assistant Community",
            entry_type=DeviceEntryType.SERVICE,
        )


class AutomationSuggestionsCountSensor(AutomationSuggestionsBaseSensor):
    """Sensor showing the count of automation suggestions."""

    _attr_icon = "mdi:counter"
    _attr_native_unit_of_measurement = "suggestions"
    _attr_translation_key = "count"

    def __init__(
        self,
        coordinator: AutomationSuggestionsCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the count sensor.

        Args:
            coordinator: The data update coordinator.
            entry: Config entry for unique ID generation.
        """
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_count"

    @property
    def native_value(self) -> int:
        """Return the number of suggestions."""
        if self.coordinator.data is None:
            return 0
        return len(self.coordinator.data)


class AutomationSuggestionsTopSensor(AutomationSuggestionsBaseSensor):
    """Sensor exposing the top automation suggestions as attributes."""

    _attr_icon = "mdi:lightbulb-auto-outline"
    _attr_translation_key = "top"

    def __init__(
        self,
        coordinator: AutomationSuggestionsCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the top suggestions sensor.

        Args:
            coordinator: The data update coordinator.
            entry: Config entry for unique ID generation.
        """
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_top"

    @property
    def native_value(self) -> int:
        """Return the count of suggestions (same as count sensor)."""
        if self.coordinator.data is None:
            return 0
        return len(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the top 5 suggestions as attributes."""
        if self.coordinator.data is None:
            return {"suggestions": []}

        # Get top 5 suggestions and convert to dict
        top_suggestions: list[Suggestion] = self.coordinator.data[:5]
        suggestions_list = [s.to_dict() for s in top_suggestions]

        return {"suggestions": suggestions_list}


class AutomationSuggestionsLastAnalysisSensor(AutomationSuggestionsBaseSensor):
    """Sensor showing the timestamp of the last analysis."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-check-outline"
    _attr_translation_key = "last_analysis"

    def __init__(
        self,
        coordinator: AutomationSuggestionsCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the last analysis sensor.

        Args:
            coordinator: The data update coordinator.
            entry: Config entry for unique ID generation.
        """
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_last_analysis"

    @property
    def native_value(self) -> datetime | None:
        """Return the timestamp of the last successful analysis."""
        # Use the coordinator's internal last_update_success tracking
        # Return None if no successful update yet
        if not self.coordinator.last_update_success:
            return None
        # Return the last_updated time from coordinator if available
        return getattr(self.coordinator, "_last_update_time", None)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the status and count of the last analysis."""
        suggestion_count = 0
        if self.coordinator.data is not None:
            suggestion_count = len(self.coordinator.data)

        if self.coordinator.last_update_success:
            return {"status": "success", "suggestion_count": suggestion_count}
        return {"status": "error", "suggestion_count": suggestion_count}
