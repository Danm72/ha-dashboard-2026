"""Sensor platform for the Automation Suggestions integration.

Provides sensors to expose automation suggestion data to Home Assistant.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
    coordinator: AutomationSuggestionsCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    entities: list[SensorEntity] = [
        AutomationSuggestionsCountSensor(coordinator, entry),
        AutomationSuggestionsTopSensor(coordinator, entry),
        AutomationSuggestionsLastAnalysisSensor(coordinator, entry),
    ]

    async_add_entities(entities)
    _LOGGER.debug("Added %d automation suggestion sensors", len(entities))


class AutomationSuggestionsCountSensor(
    CoordinatorEntity[AutomationSuggestionsCoordinator], SensorEntity
):
    """Sensor showing the count of automation suggestions."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:counter"
    _attr_native_unit_of_measurement = "suggestions"

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
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_count"
        self._attr_name = "Automation Suggestions Count"
        self.entity_id = "sensor.automation_suggestions_count"

    @property
    def native_value(self) -> int:
        """Return the number of suggestions."""
        if self.coordinator.data is None:
            return 0
        return len(self.coordinator.data)


class AutomationSuggestionsTopSensor(
    CoordinatorEntity[AutomationSuggestionsCoordinator], SensorEntity
):
    """Sensor exposing the top automation suggestions as attributes."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:lightbulb-auto-outline"

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
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_top"
        self._attr_name = "Automation Suggestions Top"
        self.entity_id = "sensor.automation_suggestions_top"

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


class AutomationSuggestionsLastAnalysisSensor(
    CoordinatorEntity[AutomationSuggestionsCoordinator], SensorEntity
):
    """Sensor showing the timestamp of the last analysis."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-check-outline"

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
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_last_analysis"
        self._attr_name = "Automation Suggestions Last Analysis"
        self.entity_id = "sensor.automation_suggestions_last_analysis"

    @property
    def native_value(self) -> str | None:
        """Return the ISO timestamp of the last successful analysis."""
        if self.coordinator.last_update_success_time is None:
            return None
        return self.coordinator.last_update_success_time.isoformat()

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the status of the last analysis."""
        if self.coordinator.last_update_success:
            return {"status": "success"}
        return {"status": "error"}
