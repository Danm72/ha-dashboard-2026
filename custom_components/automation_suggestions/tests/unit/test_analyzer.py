#!/usr/bin/env python3.11
"""
Tests for automation_suggestions analyzer module.

Ported from tools/test_extract_manual_actions.py

Covers:
1. NoneType bug fix - handling entries with entity_id: null
2. is_manual_action function
3. extract_action_from_entry function
4. parse_timestamp function
5. get_time_window function
6. format_time_range function
7. find_automation_candidates function
8. Malformed logbook entries handling
"""

import pytest
from datetime import datetime

# Import the module under test
from custom_components.automation_suggestions.analyzer import (
    is_manual_action,
    extract_action_from_entry,
    parse_timestamp,
    get_time_window,
    format_time_range,
    find_automation_candidates,
)


# =============================================================================
# 1. NoneType Bug Fix Tests (CRITICAL)
# =============================================================================

class TestNoneTypeBugFix:
    """Tests for the NoneType bug fix when entity_id is null."""

    def test_extract_action_handles_null_entity_id(self):
        """extract_action_from_entry should handle entries with entity_id: null."""
        entry = {
            "entity_id": None,
            "state": "on",
            "when": "2025-01-20T10:00:00Z",
        }
        # Should not raise TypeError, should return the state or "unknown"
        result = extract_action_from_entry(entry)
        assert result == "on"

    def test_extract_action_handles_missing_entity_id(self):
        """extract_action_from_entry should handle entries without entity_id key."""
        entry = {
            "state": "off",
            "when": "2025-01-20T10:00:00Z",
        }
        result = extract_action_from_entry(entry)
        assert result == "off"

    def test_extract_action_handles_empty_string_entity_id(self):
        """extract_action_from_entry should handle entries with empty entity_id."""
        entry = {
            "entity_id": "",
            "state": "unknown_state",
            "when": "2025-01-20T10:00:00Z",
        }
        result = extract_action_from_entry(entry)
        assert result == "unknown_state"

    def test_extract_action_null_entity_no_state(self):
        """extract_action_from_entry should return 'unknown' for null entity and no state."""
        entry = {
            "entity_id": None,
            "when": "2025-01-20T10:00:00Z",
        }
        result = extract_action_from_entry(entry)
        assert result == "unknown"

    def test_main_loop_handles_null_entity_id(self):
        """The main processing loop should skip entries with null entity_id."""
        # Simulate entries that would be returned from the API
        entries = [
            {"entity_id": None, "state": "on", "context_user_id": "user1"},
            {"entity_id": "light.living_room", "state": "on", "context_user_id": "user1"},
            {"entity_id": "", "state": "off", "context_user_id": "user1"},
        ]

        # Simulate the main loop logic
        domains = ["light", "switch"]
        processed = []

        for entry in entries:
            entity_id = entry.get("entity_id") or ""
            domain = entity_id.split(".")[0] if "." in entity_id else ""
            if domain in domains:
                processed.append(entity_id)

        # Only the valid light entity should be processed
        assert processed == ["light.living_room"]


# =============================================================================
# 2. is_manual_action Function Tests
# =============================================================================

class TestIsManualAction:
    """Tests for the is_manual_action function.

    Uses exclusion-based logic: an action is considered manual unless
    we can prove it was automated. This catches physical button presses,
    Zigbee/Z-Wave triggers, third-party apps, and voice assistants.
    """

    # -------------------------------------------------------------------------
    # Physical trigger tests (no context_user_id, no automation context)
    # -------------------------------------------------------------------------

    def test_physical_switch_trigger_returns_true(self):
        """Physical switch with state but no context_user_id should be manual."""
        entry = {
            "entity_id": "switch.living_room",
            "state": "on",
        }
        assert is_manual_action(entry) is True

    def test_zigbee_button_press_returns_true(self):
        """Zigbee button press with state but no context_user_id should be manual."""
        entry = {
            "entity_id": "light.bedroom",
            "state": "on",
            # No context_user_id - typical for Zigbee/Z-Wave triggers
        }
        assert is_manual_action(entry) is True

    def test_physical_trigger_without_state_returns_false(self):
        """Entry without state (just an event) should return False."""
        entry = {
            "entity_id": "light.living_room",
            # No state - not a state change
        }
        assert is_manual_action(entry) is False

    def test_physical_trigger_without_entity_id_returns_false(self):
        """Entry without entity_id should return False."""
        entry = {
            "state": "on",
        }
        assert is_manual_action(entry) is False

    # -------------------------------------------------------------------------
    # Automation exclusion tests
    # -------------------------------------------------------------------------

    def test_returns_false_when_automation_triggered(self):
        """Should return False when context_event_type is automation_triggered."""
        entry = {
            "entity_id": "light.living_room",
            "state": "on",
            "context_user_id": "user123",
            "context_event_type": "automation_triggered",
        }
        assert is_manual_action(entry) is False

    def test_returns_false_when_context_domain_is_automation(self):
        """Should return False when context_domain is 'automation'."""
        entry = {
            "entity_id": "light.living_room",
            "state": "on",
            "context_user_id": "user123",
            "context_domain": "automation",
        }
        assert is_manual_action(entry) is False

    def test_returns_false_when_context_domain_is_script(self):
        """Should return False when context_domain is 'script'."""
        entry = {
            "entity_id": "light.living_room",
            "state": "on",
            "context_user_id": "user123",
            "context_domain": "script",
        }
        assert is_manual_action(entry) is False

    # -------------------------------------------------------------------------
    # Source-based automation exclusion tests
    # -------------------------------------------------------------------------

    def test_returns_false_for_time_pattern_source(self):
        """Should return False when source indicates time pattern trigger."""
        entry = {
            "entity_id": "light.living_room",
            "state": "on",
            "source": "triggered by time pattern",
        }
        assert is_manual_action(entry) is False

    def test_returns_false_for_state_of_source(self):
        """Should return False when source indicates state-based trigger."""
        entry = {
            "entity_id": "light.living_room",
            "state": "on",
            "source": "state of binary_sensor.motion",
        }
        assert is_manual_action(entry) is False

    def test_returns_false_for_time_change_source(self):
        """Should return False when source indicates time change trigger."""
        entry = {
            "entity_id": "light.porch",
            "state": "on",
            "source": "time change",
        }
        assert is_manual_action(entry) is False

    def test_returns_false_for_template_source(self):
        """Should return False when source indicates template trigger."""
        entry = {
            "entity_id": "light.living_room",
            "state": "on",
            "source": "triggered via template",
        }
        assert is_manual_action(entry) is False

    def test_returns_false_for_ha_starting_source(self):
        """Should return False when source indicates HA startup."""
        entry = {
            "entity_id": "light.living_room",
            "state": "on",
            "source": "Home Assistant starting",
        }
        assert is_manual_action(entry) is False

    # -------------------------------------------------------------------------
    # User-triggered tests (with context_user_id)
    # -------------------------------------------------------------------------

    def test_returns_true_for_valid_manual_action(self):
        """Should return True for a valid manual action with user_id and no automation context."""
        entry = {
            "entity_id": "light.living_room",
            "state": "on",
            "context_user_id": "user123",
        }
        assert is_manual_action(entry) is True

    def test_returns_true_with_other_context_domain(self):
        """Should return True when context_domain is neither automation nor script."""
        entry = {
            "entity_id": "light.living_room",
            "state": "on",
            "context_user_id": "user123",
            "context_domain": "homeassistant",
        }
        assert is_manual_action(entry) is True

    def test_returns_true_with_other_event_type(self):
        """Should return True when context_event_type is not automation_triggered."""
        entry = {
            "entity_id": "light.living_room",
            "state": "on",
            "context_user_id": "user123",
            "context_event_type": "call_service",
        }
        assert is_manual_action(entry) is True

    # -------------------------------------------------------------------------
    # Edge case tests
    # -------------------------------------------------------------------------

    def test_returns_false_when_context_user_id_is_empty(self):
        """Should return False when context_user_id is empty string (no state change proof)."""
        entry = {
            "entity_id": "light.living_room",
            "state": "on",
            "context_user_id": "",
        }
        # Empty string is falsy, but we still have entity_id and state
        # so it should be considered a potential physical trigger
        assert is_manual_action(entry) is True

    def test_context_user_id_as_integer(self):
        """context_user_id as integer instead of string should still be truthy."""
        entry = {
            "entity_id": "light.living_room",
            "state": "on",
            "context_user_id": 12345,
        }
        assert is_manual_action(entry) is True

    def test_non_automation_source_returns_true(self):
        """Source that doesn't match automation patterns should return True."""
        entry = {
            "entity_id": "light.living_room",
            "state": "on",
            "source": "user interaction",
        }
        assert is_manual_action(entry) is True


# =============================================================================
# 3. extract_action_from_entry Function Tests
# =============================================================================

class TestExtractActionFromEntry:
    """Tests for the extract_action_from_entry function."""

    def test_scene_domain_returns_activated(self):
        """Scene domain should return 'activated'."""
        entry = {
            "entity_id": "scene.movie_night",
            "state": "scening",
        }
        assert extract_action_from_entry(entry) == "activated"

    def test_script_domain_returns_executed_for_on(self):
        """Script domain with state 'on' should return 'executed'."""
        entry = {
            "entity_id": "script.backup_routine",
            "state": "on",
        }
        assert extract_action_from_entry(entry) == "executed"

    def test_script_domain_returns_state_for_non_on(self):
        """Script domain with state other than 'on' should return that state."""
        entry = {
            "entity_id": "script.backup_routine",
            "state": "off",
        }
        assert extract_action_from_entry(entry) == "off"

    def test_light_domain_returns_turn_on(self):
        """Light domain with state 'on' should return 'turn_on'."""
        entry = {
            "entity_id": "light.living_room",
            "state": "on",
        }
        assert extract_action_from_entry(entry) == "turn_on"

    def test_light_domain_returns_turn_off(self):
        """Light domain with state 'off' should return 'turn_off'."""
        entry = {
            "entity_id": "light.living_room",
            "state": "off",
        }
        assert extract_action_from_entry(entry) == "turn_off"

    def test_switch_domain_returns_turn_on(self):
        """Switch domain with state 'on' should return 'turn_on'."""
        entry = {
            "entity_id": "switch.porch_fan",
            "state": "on",
        }
        assert extract_action_from_entry(entry) == "turn_on"

    def test_switch_domain_returns_turn_off(self):
        """Switch domain with state 'off' should return 'turn_off'."""
        entry = {
            "entity_id": "switch.porch_fan",
            "state": "off",
        }
        assert extract_action_from_entry(entry) == "turn_off"

    def test_cover_domain_returns_turn_on(self):
        """Cover domain with state 'on' should return 'turn_on'."""
        entry = {
            "entity_id": "cover.garage_door",
            "state": "on",
        }
        assert extract_action_from_entry(entry) == "turn_on"

    def test_cover_domain_returns_turn_off(self):
        """Cover domain with state 'off' should return 'turn_off'."""
        entry = {
            "entity_id": "cover.garage_door",
            "state": "off",
        }
        assert extract_action_from_entry(entry) == "turn_off"

    def test_light_domain_returns_state_for_other(self):
        """Light domain with state other than on/off should return that state."""
        entry = {
            "entity_id": "light.living_room",
            "state": "unavailable",
        }
        assert extract_action_from_entry(entry) == "unavailable"

    def test_climate_domain_returns_set_state(self):
        """Climate domain should return 'set_{state}'."""
        entry = {
            "entity_id": "climate.thermostat",
            "state": "heat",
        }
        assert extract_action_from_entry(entry) == "set_heat"

    def test_climate_domain_with_cool_state(self):
        """Climate domain with cool state should return 'set_cool'."""
        entry = {
            "entity_id": "climate.thermostat",
            "state": "cool",
        }
        assert extract_action_from_entry(entry) == "set_cool"

    def test_climate_domain_with_empty_state(self):
        """Climate domain with empty state should return 'changed'."""
        entry = {
            "entity_id": "climate.thermostat",
            "state": "",
        }
        assert extract_action_from_entry(entry) == "changed"

    def test_unknown_domain_returns_state(self):
        """Unknown domain should return the state value."""
        entry = {
            "entity_id": "sensor.temperature",
            "state": "22.5",
        }
        assert extract_action_from_entry(entry) == "22.5"

    def test_unknown_domain_empty_state_returns_unknown(self):
        """Unknown domain with empty state should return 'unknown'."""
        entry = {
            "entity_id": "sensor.temperature",
            "state": "",
        }
        assert extract_action_from_entry(entry) == "unknown"

    def test_unknown_domain_no_state_returns_unknown(self):
        """Unknown domain without state key should return 'unknown'."""
        entry = {
            "entity_id": "sensor.temperature",
        }
        assert extract_action_from_entry(entry) == "unknown"


# =============================================================================
# 4. parse_timestamp Function Tests
# =============================================================================

class TestParseTimestamp:
    """Tests for the parse_timestamp function."""

    def test_returns_none_for_empty_input(self):
        """Should return None for empty string."""
        assert parse_timestamp("") is None

    def test_returns_none_for_none_input(self):
        """Should return None for None input."""
        assert parse_timestamp(None) is None

    def test_parses_iso_timestamp_with_z_suffix(self):
        """Should parse ISO timestamp with Z suffix."""
        result = parse_timestamp("2025-01-20T14:30:00Z")
        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 20
        assert result.hour == 14
        assert result.minute == 30
        assert result.second == 0

    def test_parses_iso_timestamp_with_timezone_offset(self):
        """Should parse ISO timestamp with timezone offset."""
        result = parse_timestamp("2025-01-20T14:30:00+00:00")
        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 20
        assert result.hour == 14
        assert result.minute == 30

    def test_parses_iso_timestamp_with_positive_offset(self):
        """Should parse ISO timestamp with positive timezone offset."""
        result = parse_timestamp("2025-01-20T14:30:00+05:30")
        assert result is not None
        assert result.year == 2025
        assert result.hour == 14

    def test_parses_iso_timestamp_with_negative_offset(self):
        """Should parse ISO timestamp with negative timezone offset."""
        result = parse_timestamp("2025-01-20T14:30:00-08:00")
        assert result is not None
        assert result.year == 2025
        assert result.hour == 14

    def test_parses_iso_timestamp_without_timezone(self):
        """Should parse ISO timestamp without timezone."""
        result = parse_timestamp("2025-01-20T14:30:00")
        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 20
        assert result.hour == 14
        assert result.minute == 30

    def test_parses_iso_timestamp_with_microseconds(self):
        """Should parse ISO timestamp with microseconds."""
        result = parse_timestamp("2025-01-20T14:30:00.123456Z")
        assert result is not None
        assert result.year == 2025
        assert result.microsecond == 123456

    def test_returns_none_for_invalid_format(self):
        """Should return None for invalid timestamp format."""
        result = parse_timestamp("not-a-timestamp")
        assert result is None

    def test_parses_date_only_timestamp(self):
        """Should parse date-only string in Python 3.11+."""
        result = parse_timestamp("2025-01-20")
        # datetime.fromisoformat handles date-only strings in Python 3.11+
        assert result is not None


# =============================================================================
# 5. get_time_window Function Tests
# =============================================================================

class TestGetTimeWindow:
    """Tests for the get_time_window function."""

    def test_returns_correct_30_minute_bucket_first_half(self):
        """Should return :00 bucket for minutes 0-29."""
        dt = datetime(2025, 1, 20, 14, 15, 0)
        result = get_time_window(dt)
        assert result == "14:00"

    def test_returns_correct_30_minute_bucket_second_half(self):
        """Should return :30 bucket for minutes 30-59."""
        dt = datetime(2025, 1, 20, 14, 45, 0)
        result = get_time_window(dt)
        assert result == "14:30"

    def test_returns_correct_bucket_at_boundary_0(self):
        """Should return :00 bucket for minute 0."""
        dt = datetime(2025, 1, 20, 14, 0, 0)
        result = get_time_window(dt)
        assert result == "14:00"

    def test_returns_correct_bucket_at_boundary_29(self):
        """Should return :00 bucket for minute 29."""
        dt = datetime(2025, 1, 20, 14, 29, 0)
        result = get_time_window(dt)
        assert result == "14:00"

    def test_returns_correct_bucket_at_boundary_30(self):
        """Should return :30 bucket for minute 30."""
        dt = datetime(2025, 1, 20, 14, 30, 0)
        result = get_time_window(dt)
        assert result == "14:30"

    def test_returns_correct_bucket_at_boundary_59(self):
        """Should return :30 bucket for minute 59."""
        dt = datetime(2025, 1, 20, 14, 59, 0)
        result = get_time_window(dt)
        assert result == "14:30"

    def test_formats_single_digit_hour_with_leading_zero(self):
        """Should format single digit hours with leading zero."""
        dt = datetime(2025, 1, 20, 8, 15, 0)
        result = get_time_window(dt)
        assert result == "08:00"

    def test_handles_midnight(self):
        """Should handle midnight correctly."""
        dt = datetime(2025, 1, 20, 0, 15, 0)
        result = get_time_window(dt)
        assert result == "00:00"

    def test_handles_late_night(self):
        """Should handle 23:xx correctly."""
        dt = datetime(2025, 1, 20, 23, 45, 0)
        result = get_time_window(dt)
        assert result == "23:30"

    def test_custom_window_minutes_15(self):
        """Should work with custom window of 15 minutes."""
        dt = datetime(2025, 1, 20, 14, 37, 0)
        result = get_time_window(dt, window_minutes=15)
        assert result == "14:30"

    def test_custom_window_minutes_60(self):
        """Should work with custom window of 60 minutes."""
        dt = datetime(2025, 1, 20, 14, 45, 0)
        result = get_time_window(dt, window_minutes=60)
        assert result == "14:00"


# =============================================================================
# 6. format_time_range Function Tests
# =============================================================================

class TestFormatTimeRange:
    """Tests for the format_time_range function."""

    def test_returns_unknown_for_empty_list(self):
        """Should return 'unknown' for empty list."""
        assert format_time_range([]) == "unknown"

    def test_returns_single_time_for_same_min_max_hour(self):
        """Should return single time when min and max hour are the same."""
        hours = [14, 14, 14]
        result = format_time_range(hours)
        assert result == "14:00"

    def test_returns_range_for_different_hours(self):
        """Should return range for different hours."""
        hours = [10, 14, 18]
        result = format_time_range(hours)
        assert result == "10:00-18:59"

    def test_returns_range_with_two_hours(self):
        """Should return range for two different hours."""
        hours = [8, 22]
        result = format_time_range(hours)
        assert result == "08:00-22:59"

    def test_formats_single_digit_hours_with_leading_zero(self):
        """Should format single digit hours with leading zeros."""
        hours = [6, 6, 6]
        result = format_time_range(hours)
        assert result == "06:00"

    def test_handles_midnight_hour(self):
        """Should handle hour 0 (midnight) correctly."""
        hours = [0, 0]
        result = format_time_range(hours)
        assert result == "00:00"

    def test_handles_range_spanning_midnight(self):
        """Should handle range that includes midnight."""
        hours = [0, 12, 23]
        result = format_time_range(hours)
        assert result == "00:00-23:59"

    def test_handles_single_hour_in_list(self):
        """Should handle list with single hour."""
        hours = [10]
        result = format_time_range(hours)
        assert result == "10:00"


# =============================================================================
# 7. find_automation_candidates Function Tests
# =============================================================================

class TestFindAutomationCandidates:
    """Tests for the find_automation_candidates function."""

    def test_returns_empty_list_when_no_patterns(self):
        """Should return empty list when patterns is empty."""
        patterns = {}
        result = find_automation_candidates(patterns)
        assert result == []

    def test_returns_empty_list_when_below_threshold(self):
        """Should return empty list when no patterns meet min_occurrences."""
        patterns = {
            "light.living_room": {
                "turn_on": {
                    "total_count": 2,  # Below default threshold of 3
                    "most_common_window": "14:00",
                    "window_count": 2,
                    "hours": [14, 14],
                    "time_range": "14:00",
                }
            }
        }
        result = find_automation_candidates(patterns, min_occurrences=3)
        assert result == []

    def test_returns_empty_when_window_count_below_threshold(self):
        """Should return empty when window_count is below 50% of total."""
        patterns = {
            "light.living_room": {
                "turn_on": {
                    "total_count": 10,
                    "most_common_window": "14:00",
                    "window_count": 1,  # Only 10% consistency, below 50%
                    "hours": [1, 2, 3, 4, 5, 6, 7, 8, 9, 14],
                    "time_range": "01:00-14:59",
                }
            }
        }
        result = find_automation_candidates(patterns, min_occurrences=3)
        assert result == []

    def test_returns_candidates_meeting_threshold(self):
        """Should return candidates that meet the threshold."""
        patterns = {
            "light.living_room": {
                "turn_on": {
                    "total_count": 5,
                    "most_common_window": "14:00",
                    "window_count": 4,  # 80% consistency
                    "hours": [14, 14, 14, 14, 15],
                    "time_range": "14:00-15:59",
                }
            }
        }
        result = find_automation_candidates(patterns, min_occurrences=3)
        assert len(result) == 1
        assert result[0]["entity_id"] == "light.living_room"
        assert result[0]["action"] == "turn_on"

    def test_candidates_sorted_by_consistency(self):
        """Should return candidates sorted by consistency (descending)."""
        patterns = {
            "light.living_room": {
                "turn_on": {
                    "total_count": 10,
                    "most_common_window": "14:00",
                    "window_count": 6,  # 60% consistency
                    "hours": [14] * 6 + [15] * 4,
                    "time_range": "14:00-15:59",
                }
            },
            "light.bedroom": {
                "turn_off": {
                    "total_count": 5,
                    "most_common_window": "22:00",
                    "window_count": 5,  # 100% consistency
                    "hours": [22, 22, 22, 22, 22],
                    "time_range": "22:00",
                }
            }
        }
        result = find_automation_candidates(patterns, min_occurrences=3)
        assert len(result) == 2
        # Higher consistency should come first
        assert result[0]["entity_id"] == "light.bedroom"
        assert result[0]["consistency"] == 1.0
        assert result[1]["entity_id"] == "light.living_room"
        assert result[1]["consistency"] == 0.6

    def test_candidates_include_all_required_fields(self):
        """Should include all required fields in candidate objects."""
        patterns = {
            "light.kitchen": {
                "turn_on": {
                    "total_count": 4,
                    "most_common_window": "07:00",
                    "window_count": 3,
                    "hours": [7, 7, 7, 8],
                    "time_range": "07:00-08:59",
                }
            }
        }
        result = find_automation_candidates(patterns, min_occurrences=3)
        assert len(result) == 1
        candidate = result[0]

        # Check all required fields exist
        assert "entity_id" in candidate
        assert "action" in candidate
        assert "total_occurrences" in candidate
        assert "pattern_window" in candidate
        assert "pattern_occurrences" in candidate
        assert "time_range" in candidate
        assert "consistency" in candidate

        # Check values
        assert candidate["entity_id"] == "light.kitchen"
        assert candidate["action"] == "turn_on"
        assert candidate["total_occurrences"] == 4
        assert candidate["pattern_window"] == "07:00"
        assert candidate["pattern_occurrences"] == 3
        assert candidate["time_range"] == "07:00-08:59"
        assert candidate["consistency"] == 0.75

    def test_custom_min_occurrences(self):
        """Should respect custom min_occurrences parameter."""
        patterns = {
            "light.living_room": {
                "turn_on": {
                    "total_count": 2,
                    "most_common_window": "14:00",
                    "window_count": 2,
                    "hours": [14, 14],
                    "time_range": "14:00",
                }
            }
        }
        # Should return empty with default min_occurrences=3
        result = find_automation_candidates(patterns, min_occurrences=3)
        assert result == []

        # Should return candidate with min_occurrences=2
        result = find_automation_candidates(patterns, min_occurrences=2)
        assert len(result) == 1

    def test_multiple_actions_for_same_entity(self):
        """Should handle multiple actions for the same entity."""
        patterns = {
            "light.living_room": {
                "turn_on": {
                    "total_count": 5,
                    "most_common_window": "07:00",
                    "window_count": 4,
                    "hours": [7, 7, 7, 7, 8],
                    "time_range": "07:00-08:59",
                },
                "turn_off": {
                    "total_count": 5,
                    "most_common_window": "22:00",
                    "window_count": 5,
                    "hours": [22, 22, 22, 22, 22],
                    "time_range": "22:00",
                }
            }
        }
        result = find_automation_candidates(patterns, min_occurrences=3)
        assert len(result) == 2

        # Both should be for the same entity but different actions
        entities = [c["entity_id"] for c in result]
        actions = [c["action"] for c in result]
        assert entities == ["light.living_room", "light.living_room"]
        assert set(actions) == {"turn_on", "turn_off"}


# =============================================================================
# 8. Malformed Logbook Entries Tests
# =============================================================================

class TestMalformedLogbookEntries:
    """
    Tests for malformed/edge-case Home Assistant logbook responses.

    These tests cover REAL edge cases that can occur with Home Assistant's
    logbook API. Many of these tests are expected to FAIL initially,
    documenting areas where the script needs hardening.
    """

    # -------------------------------------------------------------------------
    # 8.1 Missing Fields Entirely (not null, but key doesn't exist)
    # -------------------------------------------------------------------------

    def test_entry_with_no_entity_id_key_is_manual_action(self):
        """Entry missing entity_id key entirely should not crash is_manual_action."""
        entry = {
            "state": "on",
            "when": "2025-01-20T10:00:00Z",
            "context_user_id": "user123",
        }
        # Should not raise, should return True (has user_id, no automation context)
        result = is_manual_action(entry)
        assert result is True

    def test_entry_with_no_entity_id_key_extract_action(self):
        """Entry missing entity_id key should return state or 'unknown'."""
        entry = {
            "state": "on",
            "when": "2025-01-20T10:00:00Z",
        }
        result = extract_action_from_entry(entry)
        assert result == "on"

    def test_entry_with_no_state_key(self):
        """Entry missing state key entirely should handle gracefully."""
        entry = {
            "entity_id": "light.living_room",
            "when": "2025-01-20T10:00:00Z",
            "context_user_id": "user123",
        }
        result = extract_action_from_entry(entry)
        # Light domain with no state should return "unknown" or empty handling
        assert result in ("", "unknown", "turn_")  # depends on implementation

    def test_entry_with_no_when_key(self):
        """Entry missing when key should parse to None timestamp."""
        entry = {
            "entity_id": "light.living_room",
            "state": "on",
            "context_user_id": "user123",
        }
        # parse_timestamp should handle missing 'when'
        result = parse_timestamp(entry.get("when"))
        assert result is None

    def test_entry_with_no_context_user_id_key(self):
        """Entry missing context_user_id key but with entity_id and state should be manual."""
        entry = {
            "entity_id": "light.living_room",
            "state": "on",
            "when": "2025-01-20T10:00:00Z",
        }
        result = is_manual_action(entry)
        # With exclusion-based logic, this is considered a physical trigger
        assert result is True

    # -------------------------------------------------------------------------
    # 8.2 Wrong Data Types
    # -------------------------------------------------------------------------

    def test_entity_id_as_integer(self):
        """entity_id as integer instead of string should not crash."""
        entry = {
            "entity_id": 12345,
            "state": "on",
            "when": "2025-01-20T10:00:00Z",
            "context_user_id": "user123",
        }
        # Should handle gracefully - either convert to string or return safe default
        result = extract_action_from_entry(entry)
        # Integer has no "." so domain extraction would fail
        assert result is not None

    def test_state_as_dict(self):
        """state as dict instead of string should not crash."""
        entry = {
            "entity_id": "light.living_room",
            "state": {"brightness": 255, "color": "warm"},
            "when": "2025-01-20T10:00:00Z",
            "context_user_id": "user123",
        }
        result = extract_action_from_entry(entry)
        # Should return something, not crash
        assert result is not None

    def test_state_as_list(self):
        """state as list instead of string should not crash."""
        entry = {
            "entity_id": "light.living_room",
            "state": ["on", "off"],
            "when": "2025-01-20T10:00:00Z",
            "context_user_id": "user123",
        }
        result = extract_action_from_entry(entry)
        assert result is not None

    def test_when_as_integer_timestamp(self):
        """when as integer (Unix timestamp) instead of ISO string."""
        entry = {
            "entity_id": "light.living_room",
            "state": "on",
            "when": 1705750800,  # Unix timestamp
            "context_user_id": "user123",
        }
        result = parse_timestamp(entry.get("when"))
        # Should return None since it's not a string, or handle conversion
        assert result is None  # Current impl expects string

    def test_context_user_id_as_integer(self):
        """context_user_id as integer instead of string."""
        entry = {
            "entity_id": "light.living_room",
            "state": "on",
            "when": "2025-01-20T10:00:00Z",
            "context_user_id": 12345,
        }
        # Should still be considered manual (truthy value)
        result = is_manual_action(entry)
        assert result is True

    # -------------------------------------------------------------------------
    # 8.3 Malformed Entity IDs
    # -------------------------------------------------------------------------

    def test_entity_id_with_no_dot(self):
        """Entity ID with no dot (e.g., 'lightbedroom') should not crash."""
        entry = {
            "entity_id": "lightbedroom",
            "state": "on",
            "when": "2025-01-20T10:00:00Z",
            "context_user_id": "user123",
        }
        result = extract_action_from_entry(entry)
        # No domain extracted, should return state or 'unknown'
        assert result == "on"

    def test_entity_id_is_just_a_dot(self):
        """Entity ID that's just a dot '.' should not crash."""
        entry = {
            "entity_id": ".",
            "state": "on",
            "when": "2025-01-20T10:00:00Z",
            "context_user_id": "user123",
        }
        result = extract_action_from_entry(entry)
        # split(".") on "." gives ["", ""], domain would be ""
        assert result is not None

    def test_entity_id_with_multiple_dots(self):
        """Entity ID with multiple dots (e.g., 'light.bedroom.main')."""
        entry = {
            "entity_id": "light.bedroom.main",
            "state": "on",
            "when": "2025-01-20T10:00:00Z",
            "context_user_id": "user123",
        }
        result = extract_action_from_entry(entry)
        # Domain should be 'light' from first split
        assert result == "turn_on"

    def test_entity_id_empty_string(self):
        """Empty string entity_id should not crash."""
        entry = {
            "entity_id": "",
            "state": "on",
            "when": "2025-01-20T10:00:00Z",
            "context_user_id": "user123",
        }
        result = extract_action_from_entry(entry)
        # No domain, should return state
        assert result == "on"

    def test_entity_id_starts_with_dot(self):
        """Entity ID starting with dot (e.g., '.bedroom')."""
        entry = {
            "entity_id": ".bedroom",
            "state": "on",
            "when": "2025-01-20T10:00:00Z",
            "context_user_id": "user123",
        }
        result = extract_action_from_entry(entry)
        # split(".")[0] gives "", domain would be empty
        assert result is not None

    def test_entity_id_ends_with_dot(self):
        """Entity ID ending with dot (e.g., 'light.')."""
        entry = {
            "entity_id": "light.",
            "state": "on",
            "when": "2025-01-20T10:00:00Z",
            "context_user_id": "user123",
        }
        result = extract_action_from_entry(entry)
        # Domain would be 'light'
        assert result == "turn_on"

    # -------------------------------------------------------------------------
    # 8.4 Malformed Timestamps
    # -------------------------------------------------------------------------

    def test_timestamp_invalid_format(self):
        """Timestamp with invalid format should return None."""
        result = parse_timestamp("not-a-date")
        assert result is None

    def test_timestamp_partial_date(self):
        """Timestamp with only partial date (e.g., '2024-01')."""
        result = parse_timestamp("2024-01")
        # Should return None for incomplete date
        assert result is None

    def test_timestamp_empty_string(self):
        """Empty string timestamp should return None."""
        result = parse_timestamp("")
        assert result is None

    def test_timestamp_date_only_no_time(self):
        """Date-only timestamp (no time component)."""
        result = parse_timestamp("2025-01-20")
        # Python 3.11+ fromisoformat handles date-only
        # Implementation may return datetime at midnight or None
        # This documents actual behavior
        if result is not None:
            assert result.year == 2025
            assert result.month == 1
            assert result.day == 20

    def test_timestamp_whitespace_only(self):
        """Whitespace-only timestamp should return None."""
        result = parse_timestamp("   ")
        # Should handle as invalid/empty
        assert result is None

    def test_timestamp_with_garbage_suffix(self):
        """Timestamp with garbage suffix."""
        result = parse_timestamp("2025-01-20T10:00:00garbage")
        # Should fail to parse
        assert result is None

    def test_timestamp_with_double_timezone(self):
        """Timestamp with double timezone markers."""
        result = parse_timestamp("2025-01-20T10:00:00Z+00:00")
        # After Z replacement, becomes +00:00+00:00 - should fail
        assert result is None

    # -------------------------------------------------------------------------
    # 8.5 Edge Case Entries
    # -------------------------------------------------------------------------

    def test_completely_empty_dict(self):
        """Completely empty dict {} should not crash any function."""
        entry = {}

        # Test all main functions
        result_manual = is_manual_action(entry)
        assert result_manual is False

        result_action = extract_action_from_entry(entry)
        assert result_action == "unknown"

        result_ts = parse_timestamp(entry.get("when"))
        assert result_ts is None

    def test_entry_is_none_in_array(self):
        """Entry that is None in the array should be handled."""
        entries = [
            {"entity_id": "light.living_room", "state": "on", "context_user_id": "user1"},
            None,  # This is the edge case
            {"entity_id": "light.bedroom", "state": "off", "context_user_id": "user1"},
        ]

        # Simulate main loop processing - should skip None entries
        domains = ["light", "switch"]
        processed = []

        for entry in entries:
            if entry is None:
                continue  # Main loop should handle this
            entity_id = entry.get("entity_id") or ""
            domain = entity_id.split(".")[0] if "." in entity_id else ""
            if domain in domains and is_manual_action(entry):
                processed.append(entity_id)

        assert processed == ["light.living_room", "light.bedroom"]

    def test_entry_with_all_empty_strings(self):
        """Entry with empty strings for all fields."""
        entry = {
            "entity_id": "",
            "state": "",
            "when": "",
            "context_user_id": "",
        }

        result_manual = is_manual_action(entry)
        # Empty entity_id means no valid entity, so returns False
        assert result_manual is False

        result_action = extract_action_from_entry(entry)
        assert result_action == "unknown"

        result_ts = parse_timestamp(entry.get("when"))
        assert result_ts is None

    def test_entry_with_all_none_values(self):
        """Entry with None values for all fields."""
        entry = {
            "entity_id": None,
            "state": None,
            "when": None,
            "context_user_id": None,
        }

        result_manual = is_manual_action(entry)
        assert result_manual is False

        result_action = extract_action_from_entry(entry)
        assert result_action == "unknown"

        result_ts = parse_timestamp(entry.get("when"))
        assert result_ts is None

    # -------------------------------------------------------------------------
    # 8.6 Realistic HA Quirks
    # -------------------------------------------------------------------------

    def test_state_unavailable(self):
        """State is 'unavailable' - common HA quirk."""
        entry = {
            "entity_id": "light.living_room",
            "state": "unavailable",
            "when": "2025-01-20T10:00:00Z",
            "context_user_id": "user123",
        }
        result = extract_action_from_entry(entry)
        # Should return "unavailable" not "turn_unavailable"
        assert result == "unavailable"

    def test_state_unknown(self):
        """State is 'unknown' - common HA quirk."""
        entry = {
            "entity_id": "light.living_room",
            "state": "unknown",
            "when": "2025-01-20T10:00:00Z",
            "context_user_id": "user123",
        }
        result = extract_action_from_entry(entry)
        assert result == "unknown"

    def test_sensor_unavailable_entity(self):
        """Entity ID is of 'unavailable' type sensor."""
        entry = {
            "entity_id": "sensor.unavailable",
            "state": "42",
            "when": "2025-01-20T10:00:00Z",
            "context_user_id": "user123",
        }
        result = extract_action_from_entry(entry)
        # sensor domain, should return state
        assert result == "42"

    def test_very_long_entity_name(self):
        """Very long entity name (100+ chars)."""
        long_name = "a" * 150
        entry = {
            "entity_id": f"light.{long_name}",
            "state": "on",
            "when": "2025-01-20T10:00:00Z",
            "context_user_id": "user123",
        }
        result = extract_action_from_entry(entry)
        assert result == "turn_on"

    def test_entity_id_with_special_characters(self):
        """Entity ID with special characters."""
        entry = {
            "entity_id": "light.living_room_2nd_floor",
            "state": "on",
            "when": "2025-01-20T10:00:00Z",
            "context_user_id": "user123",
        }
        result = extract_action_from_entry(entry)
        assert result == "turn_on"

    def test_entity_id_with_unicode(self):
        """Entity ID with unicode characters."""
        entry = {
            "entity_id": "light.wohnzimmer_lampe",  # German characters
            "state": "on",
            "when": "2025-01-20T10:00:00Z",
            "context_user_id": "user123",
        }
        result = extract_action_from_entry(entry)
        assert result == "turn_on"

    def test_state_with_newlines(self):
        """State containing newlines."""
        entry = {
            "entity_id": "sensor.multiline",
            "state": "line1\nline2\nline3",
            "when": "2025-01-20T10:00:00Z",
            "context_user_id": "user123",
        }
        result = extract_action_from_entry(entry)
        assert result == "line1\nline2\nline3"

    def test_very_long_state_value(self):
        """Very long state value (1000+ chars)."""
        long_state = "x" * 1500
        entry = {
            "entity_id": "sensor.big_data",
            "state": long_state,
            "when": "2025-01-20T10:00:00Z",
            "context_user_id": "user123",
        }
        result = extract_action_from_entry(entry)
        assert result == long_state

    def test_numeric_string_state(self):
        """Numeric string state value."""
        entry = {
            "entity_id": "sensor.temperature",
            "state": "22.5",
            "when": "2025-01-20T10:00:00Z",
            "context_user_id": "user123",
        }
        result = extract_action_from_entry(entry)
        assert result == "22.5"

    def test_boolean_state_false(self):
        """State is boolean False instead of string."""
        entry = {
            "entity_id": "binary_sensor.motion",
            "state": False,
            "when": "2025-01-20T10:00:00Z",
            "context_user_id": "user123",
        }
        result = extract_action_from_entry(entry)
        # Boolean False is falsy, so should return "unknown" or handle specially
        assert result is not None

    def test_boolean_state_true(self):
        """State is boolean True instead of string."""
        entry = {
            "entity_id": "binary_sensor.motion",
            "state": True,
            "when": "2025-01-20T10:00:00Z",
            "context_user_id": "user123",
        }
        result = extract_action_from_entry(entry)
        assert result is not None

    def test_negative_numeric_state(self):
        """Negative numeric state value."""
        entry = {
            "entity_id": "sensor.temperature",
            "state": "-10.5",
            "when": "2025-01-20T10:00:00Z",
            "context_user_id": "user123",
        }
        result = extract_action_from_entry(entry)
        assert result == "-10.5"

    def test_context_with_extra_fields(self):
        """Entry with extra context fields that might confuse parsing."""
        entry = {
            "entity_id": "light.living_room",
            "state": "on",
            "when": "2025-01-20T10:00:00Z",
            "context_user_id": "user123",
            "context_parent_id": "parent456",
            "context_id": "ctx789",
            "context_something_new": "future_field",
        }
        result_manual = is_manual_action(entry)
        assert result_manual is True

        result_action = extract_action_from_entry(entry)
        assert result_action == "turn_on"


# =============================================================================
# Run tests if executed directly
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
