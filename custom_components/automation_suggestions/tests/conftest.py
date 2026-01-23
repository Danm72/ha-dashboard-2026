"""Root fixtures for automation_suggestions tests."""

import pytest

from custom_components.automation_suggestions.analyzer import Suggestion
from custom_components.automation_suggestions.const import (
    CONF_ANALYSIS_INTERVAL,
    CONF_CONSISTENCY_THRESHOLD,
    CONF_LOOKBACK_DAYS,
    CONF_MIN_OCCURRENCES,
)


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
def mock_suggestions():
    """Return mock Suggestion objects."""
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
            id="light_bedroom_turn_off_22_30",
            entity_id="light.bedroom",
            action="turn_off",
            suggested_time="22:30",
            time_window_start="22:15",
            time_window_end="22:45",
            consistency_score=0.92,
            occurrence_count=18,
            last_occurrence="2026-01-20T22:32:00+00:00",
        ),
        Suggestion(
            id="switch_coffee_turn_on_06_45",
            entity_id="switch.coffee_maker",
            action="turn_on",
            suggested_time="06:45",
            time_window_start="06:30",
            time_window_end="07:00",
            consistency_score=0.78,
            occurrence_count=8,
            last_occurrence="2026-01-20T06:48:00+00:00",
        ),
    ]


@pytest.fixture
def empty_suggestions():
    """Return empty suggestion list."""
    return []


@pytest.fixture
def mock_logbook_entries():
    """Return mock logbook API response."""
    return [
        {
            "entity_id": "light.kitchen",
            "state": "on",
            "when": "2026-01-20T07:05:00+00:00",
            "context_user_id": "user123",
        },
        {
            "entity_id": "light.kitchen",
            "state": "on",
            "when": "2026-01-21T07:02:00+00:00",
            "context_user_id": "user123",
        },
        {
            "entity_id": "light.bedroom",
            "state": "off",
            "when": "2026-01-20T22:30:00+00:00",
            "context_user_id": "user123",
        },
    ]
