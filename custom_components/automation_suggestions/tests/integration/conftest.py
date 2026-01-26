"""Integration test fixtures using pytest-homeassistant-custom-component."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.automation_suggestions.const import (
    CONF_ANALYSIS_INTERVAL,
    CONF_CONSISTENCY_THRESHOLD,
    CONF_IGNORE_AUTOMATION_PATTERNS,
    CONF_LOOKBACK_DAYS,
    CONF_MIN_OCCURRENCES,
    CONF_STALE_THRESHOLD_DAYS,
    DEFAULT_IGNORE_AUTOMATION_PATTERNS,
    DEFAULT_STALE_THRESHOLD_DAYS,
    DOMAIN,
)


@pytest.fixture
def mock_config_data():
    """Return standard config data for tests."""
    return {
        CONF_ANALYSIS_INTERVAL: 7,
        CONF_LOOKBACK_DAYS: 14,
        CONF_MIN_OCCURRENCES: 5,
        CONF_CONSISTENCY_THRESHOLD: 0.70,
        CONF_STALE_THRESHOLD_DAYS: DEFAULT_STALE_THRESHOLD_DAYS,
        CONF_IGNORE_AUTOMATION_PATTERNS: DEFAULT_IGNORE_AUTOMATION_PATTERNS,
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
    """Return sample suggestions for tests.

    Includes suggestions with varying confidence scores:
    - suggestion 1: consistency_score=0.85 (high, above 80% threshold)
    - suggestion 2: consistency_score=0.72 (medium)
    - suggestion 3: consistency_score=0.65 (low)
    """
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
            consistency_score=0.72,
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
            consistency_score=0.65,
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
    """Mock the Store for persistence (v2 format with dismissed_stale)."""
    with patch("custom_components.automation_suggestions.coordinator.Store") as mock_store_class:
        mock_store = AsyncMock()
        mock_store.async_load = AsyncMock(return_value={"dismissed": [], "dismissed_stale": []})
        mock_store.async_save = AsyncMock()
        mock_store_class.return_value = mock_store
        yield mock_store


@pytest.fixture
def mock_store_v1():
    """Mock the Store with v1 format (no dismissed_stale key)."""
    with patch("custom_components.automation_suggestions.coordinator.Store") as mock_store_class:
        mock_store = AsyncMock()
        mock_store.async_load = AsyncMock(return_value={"dismissed": ["old_suggestion"]})
        mock_store.async_save = AsyncMock()
        mock_store_class.return_value = mock_store
        yield mock_store


@pytest.fixture
def mock_stale_automations():
    """Return sample StaleAutomation instances for tests."""
    from custom_components.automation_suggestions.analyzer import StaleAutomation

    return [
        StaleAutomation(
            automation_id="automation.old_backup",
            friendly_name="Old Backup Automation",
            last_triggered="2025-12-01T10:00:00+00:00",
            days_since_triggered=56,
            is_disabled=False,
        ),
        StaleAutomation(
            automation_id="automation.never_triggered",
            friendly_name="Never Triggered",
            last_triggered=None,
            days_since_triggered=999,
            is_disabled=True,
        ),
        StaleAutomation(
            automation_id="automation.disabled_old",
            friendly_name="Disabled Old Automation",
            last_triggered="2025-11-15T08:30:00+00:00",
            days_since_triggered=72,
            is_disabled=True,
        ),
    ]


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
