"""Tests for service handlers."""

from unittest.mock import patch

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

    @pytest.mark.asyncio
    async def test_dismiss_stale_automation(self, hass, config_entry, mock_analyzer, mock_store):
        """Test dismiss service works with automation.* IDs (stale automations)."""
        from custom_components.automation_suggestions.analyzer import StaleAutomation

        config_entry.add_to_hass(hass)

        # Mock find_stale_automations to return a stale automation
        stale_result = [
            StaleAutomation(
                automation_id="automation.old_backup",
                friendly_name="Old Backup Automation",
                last_triggered="2025-12-01T10:00:00+00:00",
                days_since_triggered=56,
                is_disabled=False,
            ),
        ]

        with patch(
            "custom_components.automation_suggestions.coordinator.find_stale_automations",
            return_value=stale_result,
        ):
            await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        # Dismiss the stale automation
        await hass.services.async_call(
            DOMAIN,
            "dismiss",
            {"suggestion_id": "automation.old_backup"},
            blocking=True,
        )

        coordinator = config_entry.runtime_data
        # Should be in _dismissed_stale, not _dismissed
        assert "automation.old_backup" in coordinator._dismissed_stale
        assert "automation.old_backup" not in coordinator.dismissed

    @pytest.mark.asyncio
    async def test_dismiss_stale_persists(self, hass, config_entry, mock_analyzer, mock_store):
        """Test dismissed stale automation is persisted to storage."""
        from custom_components.automation_suggestions.analyzer import StaleAutomation

        config_entry.add_to_hass(hass)

        # Mock find_stale_automations to return a stale automation
        stale_result = [
            StaleAutomation(
                automation_id="automation.old_backup",
                friendly_name="Old Backup Automation",
                last_triggered="2025-12-01T10:00:00+00:00",
                days_since_triggered=56,
                is_disabled=False,
            ),
        ]

        with patch(
            "custom_components.automation_suggestions.coordinator.find_stale_automations",
            return_value=stale_result,
        ):
            await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        # Dismiss the stale automation
        await hass.services.async_call(
            DOMAIN,
            "dismiss",
            {"suggestion_id": "automation.old_backup"},
            blocking=True,
        )

        # Verify storage was called with both dismissed and dismissed_stale
        mock_store.async_save.assert_called()
        save_call_args = mock_store.async_save.call_args[0][0]
        assert "dismissed_stale" in save_call_args
        assert "automation.old_backup" in save_call_args["dismissed_stale"]

    @pytest.mark.asyncio
    async def test_dismiss_regular_suggestion_not_in_dismissed_stale(
        self, hass, config_entry, mock_analyzer, mock_store
    ):
        """Test that regular suggestions go to dismissed, not dismissed_stale."""
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Dismiss a regular suggestion (not starting with automation.)
        await hass.services.async_call(
            DOMAIN,
            "dismiss",
            {"suggestion_id": "light_kitchen_turn_on_07_00"},
            blocking=True,
        )

        coordinator = config_entry.runtime_data
        # Should be in _dismissed, not _dismissed_stale
        assert "light_kitchen_turn_on_07_00" in coordinator.dismissed
        assert "light_kitchen_turn_on_07_00" not in coordinator._dismissed_stale
