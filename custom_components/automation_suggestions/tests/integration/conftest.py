"""Integration test fixtures using pytest-homeassistant-custom-component."""

import pytest
from unittest.mock import AsyncMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.automation_suggestions.const import (
    DOMAIN,
    CONF_ANALYSIS_INTERVAL,
    CONF_LOOKBACK_DAYS,
    CONF_MIN_OCCURRENCES,
    CONF_CONSISTENCY_THRESHOLD,
)

# pytest_plugins moved to root conftest.py


@pytest.fixture
def mock_config_data():
    """Return standard config data for tests."""
    return {
        CONF_ANALYSIS_INTERVAL: 7,
        CONF_LOOKBACK_DAYS: 14,
        CONF_MIN_OCCURRENCES: 5,
        CONF_CONSISTENCY_THRESHOLD: 0.70,
    }


@pytest.fixture
def config_entry(mock_config_data):
    """Create a MockConfigEntry for integration tests."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data,
        options={},
        unique_id=DOMAIN,
        title="Automation Suggestions",
    )


@pytest.fixture
def mock_analyzer(mock_suggestions):
    """Mock the analyze_patterns_async function."""
    with patch(
        "custom_components.automation_suggestions.coordinator.analyze_patterns_async",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = mock_suggestions
        yield mock


@pytest.fixture
def mock_suggestions():
    """Return sample suggestions for tests."""
    from custom_components.automation_suggestions.analyzer import Suggestion

    return [
        Suggestion(
            id="light_kitchen_turn_on_07_00",
            entity_id="light.kitchen",
            action="turn_on",
            suggested_time="07:00",
            time_window_start="06:45",
            time_window_end="07:15",
            consistency_score=0.85,
            occurrence_count=12,
            last_occurrence="2026-01-20T07:05:00+00:00",
        ),
        Suggestion(
            id="light_living_room_turn_off_22_30",
            entity_id="light.living_room",
            action="turn_off",
            suggested_time="22:30",
            time_window_start="22:15",
            time_window_end="22:45",
            consistency_score=0.78,
            occurrence_count=10,
            last_occurrence="2026-01-20T22:32:00+00:00",
        ),
        Suggestion(
            id="switch_fan_turn_on_08_00",
            entity_id="switch.fan",
            action="turn_on",
            suggested_time="08:00",
            time_window_start="07:45",
            time_window_end="08:15",
            consistency_score=0.72,
            occurrence_count=8,
            last_occurrence="2026-01-19T08:02:00+00:00",
        ),
    ]


@pytest.fixture
def empty_suggestions():
    """Return empty suggestions list for tests."""
    return []


@pytest.fixture
def mock_store():
    """Mock the Store for persistence."""
    with patch(
        "custom_components.automation_suggestions.coordinator.Store"
    ) as mock_store_class:
        mock_store = AsyncMock()
        mock_store.async_load = AsyncMock(return_value={"dismissed": [], "notified": []})
        mock_store.async_save = AsyncMock()
        mock_store_class.return_value = mock_store
        yield mock_store


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Automatically enable custom integrations for all tests in this module."""
    yield


@pytest.fixture(autouse=True)
def mock_recorder_dependency(hass):
    """Mock the recorder integration to satisfy dependencies."""
    hass.data["recorder_instance"] = AsyncMock()
    # Mark recorder as loaded
    hass.config.components.add("recorder")


@pytest.fixture(autouse=True)
def mock_logbook_dependency(hass):
    """Mock the logbook integration to satisfy dependencies."""
    # Mark logbook as loaded
    hass.config.components.add("logbook")
