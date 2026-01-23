"""Tests for the data update coordinator."""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import timedelta

from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.automation_suggestions.coordinator import (
    AutomationSuggestionsCoordinator,
)
from custom_components.automation_suggestions.const import DOMAIN


class TestCoordinator:
    """Test the data update coordinator."""

    @pytest.mark.asyncio
    async def test_coordinator_init(self, hass, config_entry, mock_store):
        """Test coordinator initializes correctly."""
        config_entry.add_to_hass(hass)

        coordinator = AutomationSuggestionsCoordinator(hass, config_entry)

        assert coordinator.name == DOMAIN
        assert coordinator.update_interval == timedelta(days=7)

    @pytest.mark.asyncio
    async def test_coordinator_update_success(self, hass, config_entry, mock_analyzer, mock_store, mock_suggestions):
        """Test successful coordinator update."""
        config_entry.add_to_hass(hass)

        coordinator = AutomationSuggestionsCoordinator(hass, config_entry)
        await coordinator.async_load_persisted()
        await coordinator.async_config_entry_first_refresh()

        assert coordinator.data is not None
        assert len(coordinator.data) == 3
        mock_analyzer.assert_called_once()

    @pytest.mark.asyncio
    async def test_coordinator_update_error_handling(self, hass, config_entry, mock_store):
        """Test coordinator handles analysis errors gracefully."""
        config_entry.add_to_hass(hass)

        with patch(
            "custom_components.automation_suggestions.coordinator.analyze_patterns_async",
            side_effect=Exception("Logbook API error"),
        ):
            coordinator = AutomationSuggestionsCoordinator(hass, config_entry)
            await coordinator.async_load_persisted()

            with pytest.raises(UpdateFailed):
                await coordinator.async_config_entry_first_refresh()

    @pytest.mark.asyncio
    async def test_dismissed_suggestions_persist(self, hass, config_entry, mock_analyzer, mock_store):
        """Test dismissed suggestions are persisted."""
        config_entry.add_to_hass(hass)

        coordinator = AutomationSuggestionsCoordinator(hass, config_entry)
        await coordinator.async_load_persisted()

        await coordinator.async_dismiss("light_kitchen_turn_on_07_00")

        assert "light_kitchen_turn_on_07_00" in coordinator.dismissed
        mock_store.async_save.assert_called()

    @pytest.mark.asyncio
    async def test_load_persisted_restores_data(self, hass, config_entry):
        """Test loading persisted suggestions from storage."""
        config_entry.add_to_hass(hass)

        with patch(
            "custom_components.automation_suggestions.coordinator.Store"
        ) as mock_store_class:
            mock_store = AsyncMock()
            mock_store.async_load = AsyncMock(return_value={
                "dismissed": ["suggestion_1", "suggestion_2"],
                "notified": ["suggestion_3"],
            })
            mock_store_class.return_value = mock_store

            coordinator = AutomationSuggestionsCoordinator(hass, config_entry)
            await coordinator.async_load_persisted()

            assert "suggestion_1" in coordinator.dismissed
            assert "suggestion_2" in coordinator.dismissed
            assert "suggestion_3" in coordinator.notified

    @pytest.mark.asyncio
    async def test_clear_dismissed(self, hass, config_entry, mock_analyzer, mock_store):
        """Test clearing dismissed suggestions."""
        config_entry.add_to_hass(hass)

        coordinator = AutomationSuggestionsCoordinator(hass, config_entry)
        await coordinator.async_load_persisted()
        coordinator._dismissed = {"suggestion_1", "suggestion_2"}

        await coordinator.async_clear_dismissed()

        assert len(coordinator.dismissed) == 0
        mock_store.async_save.assert_called()
