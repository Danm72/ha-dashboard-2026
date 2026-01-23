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
