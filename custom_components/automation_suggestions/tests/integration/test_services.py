"""Tests for service handlers."""

import pytest

from custom_components.automation_suggestions.const import DOMAIN


class TestServices:
    """Test service handlers."""

    @pytest.mark.asyncio
    async def test_analyze_now_service(self, hass, config_entry, mock_analyzer, mock_store):
        """Test analyze_now service triggers immediate analysis."""
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Reset mock to track new calls
        mock_analyzer.reset_mock()

        await hass.services.async_call(
            DOMAIN,
            "analyze_now",
            {},
            blocking=True,
        )

        assert mock_analyzer.call_count >= 1

    @pytest.mark.asyncio
    async def test_dismiss_service(self, hass, config_entry, mock_analyzer, mock_store):
        """Test dismiss service hides a suggestion."""
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            DOMAIN,
            "dismiss",
            {"suggestion_id": "light_kitchen_turn_on_07_00"},
            blocking=True,
        )

        coordinator = config_entry.runtime_data
        assert "light_kitchen_turn_on_07_00" in coordinator.dismissed

    @pytest.mark.asyncio
    async def test_dismiss_service_requires_suggestion_id(
        self, hass, config_entry, mock_analyzer, mock_store
    ):
        """Test dismiss service requires suggestion_id."""
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        with pytest.raises(Exception):  # voluptuous validation error
            await hass.services.async_call(
                DOMAIN,
                "dismiss",
                {},
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_service_without_integration(self, hass):
        """Test service fails gracefully when integration not loaded."""
        # Services shouldn't be registered if integration isn't set up
        assert not hass.services.has_service(DOMAIN, "analyze_now")
