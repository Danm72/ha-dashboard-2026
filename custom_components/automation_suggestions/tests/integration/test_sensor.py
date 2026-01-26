"""Tests for sensor entities."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import STATE_UNKNOWN


class TestCountSensor:
    """Test the suggestions count sensor."""

    @pytest.mark.asyncio
    async def test_count_sensor_state(
        self, hass, config_entry, mock_analyzer, mock_store, mock_suggestions
    ):
        """Test count sensor reflects suggestion count."""
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.automation_suggestions_count")
        assert state is not None
        assert state.state == "3"
        assert state.attributes.get("unit_of_measurement") == "suggestions"

    @pytest.mark.asyncio
    async def test_count_sensor_zero_when_empty(
        self, hass, config_entry, mock_store, empty_suggestions
    ):
        """Test count sensor is 0 when no suggestions."""
        config_entry.add_to_hass(hass)

        with patch(
            "custom_components.automation_suggestions.coordinator.analyze_patterns_async",
            new_callable=AsyncMock,
            return_value=empty_suggestions,
        ):
            await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        state = hass.states.get("sensor.automation_suggestions_count")
        assert state is not None
        assert state.state == "0"


class TestTopSensor:
    """Test the top suggestions sensor."""

    @pytest.mark.asyncio
    async def test_top_sensor_attributes(
        self, hass, config_entry, mock_analyzer, mock_store, mock_suggestions
    ):
        """Test top sensor has suggestions in attributes."""
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.automation_suggestions_top")
        assert state is not None

        suggestions = state.attributes.get("suggestions", [])
        assert len(suggestions) == 3

        # Verify suggestion structure
        first = suggestions[0]
        assert "entity_id" in first
        assert "action" in first
        assert "consistency_score" in first

    @pytest.mark.asyncio
    async def test_top_sensor_limits_to_five(self, hass, config_entry, mock_store):
        """Test top sensor limits to 5 suggestions."""
        from custom_components.automation_suggestions.analyzer import Suggestion

        many_suggestions = [
            Suggestion(
                id=f"light_{i}_turn_on_07_00",
                entity_id=f"light.light_{i}",
                action="turn_on",
                suggested_time="07:00",
                time_window_start="06:45",
                time_window_end="07:15",
                consistency_score=0.85 - (i * 0.01),
                occurrence_count=10 - i,
                last_occurrence="2026-01-20T07:05:00+00:00",
            )
            for i in range(10)
        ]

        config_entry.add_to_hass(hass)

        with patch(
            "custom_components.automation_suggestions.coordinator.analyze_patterns_async",
            new_callable=AsyncMock,
            return_value=many_suggestions,
        ):
            await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        state = hass.states.get("sensor.automation_suggestions_top")
        suggestions = state.attributes.get("suggestions", [])
        assert len(suggestions) == 5


class TestBinarySensor:
    """Test the availability binary sensor."""

    @pytest.mark.asyncio
    async def test_binary_sensor_on_when_suggestions_exist(
        self, hass, config_entry, mock_analyzer, mock_store, mock_suggestions
    ):
        """Test binary sensor is on when suggestions exist."""
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("binary_sensor.automation_suggestions_available")
        assert state is not None
        assert state.state == "on"

    @pytest.mark.asyncio
    async def test_binary_sensor_off_when_no_suggestions(
        self, hass, config_entry, mock_store, empty_suggestions
    ):
        """Test binary sensor is off when no suggestions."""
        config_entry.add_to_hass(hass)

        with patch(
            "custom_components.automation_suggestions.coordinator.analyze_patterns_async",
            new_callable=AsyncMock,
            return_value=empty_suggestions,
        ):
            await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        state = hass.states.get("binary_sensor.automation_suggestions_available")
        assert state is not None
        assert state.state == "off"


class TestLastAnalysisSensor:
    """Test the last analysis timestamp sensor."""

    @pytest.mark.asyncio
    async def test_last_analysis_timestamp(
        self, hass, config_entry, mock_analyzer, mock_store, mock_suggestions
    ):
        """Test last analysis sensor shows timestamp."""
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.automation_suggestions_last_analysis")
        assert state is not None
        assert state.state != STATE_UNKNOWN
        assert state.attributes.get("status") == "success"


class TestStaleCountSensor:
    """Test the stale automations count sensor."""

    @pytest.mark.asyncio
    async def test_stale_count_sensor_state(
        self, hass, config_entry, mock_analyzer, mock_store, mock_stale_automations
    ):
        """Test stale count sensor reflects stale automation count."""
        config_entry.add_to_hass(hass)

        # Mock find_stale_automations to return our test data
        with patch(
            "custom_components.automation_suggestions.coordinator.find_stale_automations",
            return_value=mock_stale_automations[:2],  # Use first 2 from fixture
        ):
            await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        state = hass.states.get("sensor.automation_suggestions_stale_automations_count")
        assert state is not None
        # Should show count of stale automations (2 from mocked return)
        assert int(state.state) == 2
        assert state.attributes.get("unit_of_measurement") == "automations"

    @pytest.mark.asyncio
    async def test_stale_count_sensor_attributes(
        self, hass, config_entry, mock_analyzer, mock_store, mock_stale_automations
    ):
        """Test stale count sensor has stale_automations in extra_state_attributes."""
        config_entry.add_to_hass(hass)

        # Mock find_stale_automations to return a single stale automation
        with patch(
            "custom_components.automation_suggestions.coordinator.find_stale_automations",
            return_value=[mock_stale_automations[0]],
        ):
            await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        state = hass.states.get("sensor.automation_suggestions_stale_automations_count")
        assert state is not None

        stale_automations = state.attributes.get("stale_automations", [])
        assert len(stale_automations) == 1

        # Verify stale automation structure
        first = stale_automations[0]
        assert "automation_id" in first
        assert "friendly_name" in first
        assert "last_triggered" in first
        assert "days_since_triggered" in first
        assert "is_disabled" in first
        assert first["automation_id"] == "automation.old_backup"

    @pytest.mark.asyncio
    async def test_stale_count_sensor_zero_when_empty(
        self, hass, config_entry, mock_analyzer, mock_store
    ):
        """Test stale count sensor is 0 when no stale automations."""
        config_entry.add_to_hass(hass)

        # Mock find_stale_automations to return empty list
        with patch(
            "custom_components.automation_suggestions.coordinator.find_stale_automations",
            return_value=[],
        ):
            await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        state = hass.states.get("sensor.automation_suggestions_stale_automations_count")
        assert state is not None
        assert state.state == "0"
        assert state.attributes.get("stale_automations") == []

    @pytest.mark.asyncio
    async def test_stale_count_excludes_dismissed(
        self, hass, config_entry, mock_analyzer, mock_stale_automations
    ):
        """Test stale count excludes dismissed stale automations."""
        from custom_components.automation_suggestions.analyzer import StaleAutomation

        config_entry.add_to_hass(hass)

        # Create two stale automations for testing
        stale_list = [
            StaleAutomation(
                automation_id="automation.old_backup",
                friendly_name="Old Backup Automation",
                last_triggered="2025-12-01T10:00:00+00:00",
                days_since_triggered=56,
                is_disabled=False,
            ),
            StaleAutomation(
                automation_id="automation.another_old",
                friendly_name="Another Old Automation",
                last_triggered="2025-11-01T10:00:00+00:00",
                days_since_triggered=86,
                is_disabled=False,
            ),
        ]

        # Mock storage with a dismissed stale automation
        with patch(
            "custom_components.automation_suggestions.coordinator.Store"
        ) as mock_store_class:
            mock_store = AsyncMock()
            mock_store.async_load = AsyncMock(
                return_value={
                    "dismissed": [],
                    "dismissed_stale": ["automation.old_backup"],
                }
            )
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store

            # Mock find_stale_automations to return both stale automations
            with patch(
                "custom_components.automation_suggestions.coordinator.find_stale_automations",
                return_value=stale_list,
            ):
                await hass.config_entries.async_setup(config_entry.entry_id)
                await hass.async_block_till_done()

        state = hass.states.get("sensor.automation_suggestions_stale_automations_count")
        assert state is not None
        # Should be 1 because one is dismissed
        assert state.state == "1"

        stale_automations = state.attributes.get("stale_automations", [])
        assert len(stale_automations) == 1
        assert stale_automations[0]["automation_id"] == "automation.another_old"
