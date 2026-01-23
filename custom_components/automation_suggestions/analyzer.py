"""Pattern analyzer for the Automation Suggestions integration.

This module analyzes Home Assistant logbook/history data to identify
manual user actions that follow consistent timing patterns, suggesting
them as automation candidates.

The sync functions (is_manual_action, extract_action_from_entry, etc.)
are designed to be testable without Home Assistant dependencies.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

# Import constants with fallback for standalone testing
try:
    from .const import (
        DEFAULT_TIME_WINDOW_MINUTES,
        TRACKED_DOMAINS,
    )
except ImportError:
    # Defaults for standalone testing
    DEFAULT_TIME_WINDOW_MINUTES = 30
    TRACKED_DOMAINS = [
        "light", "switch", "cover", "climate", "scene", "script",
        "input_number", "input_boolean", "input_select",
        "input_datetime", "input_button"
    ]

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


@dataclass
class Suggestion:
    """Represents an automation suggestion based on detected patterns."""

    id: str
    entity_id: str
    action: str
    suggested_time: str
    time_window_start: str
    time_window_end: str
    consistency_score: float
    occurrence_count: int
    last_occurrence: str

    def to_dict(self) -> dict[str, Any]:
        """Convert suggestion to dictionary for serialization."""
        return {
            "id": self.id,
            "entity_id": self.entity_id,
            "action": self.action,
            "suggested_time": self.suggested_time,
            "time_window_start": self.time_window_start,
            "time_window_end": self.time_window_end,
            "consistency_score": self.consistency_score,
            "occurrence_count": self.occurrence_count,
            "last_occurrence": self.last_occurrence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Suggestion:
        """Create suggestion from dictionary."""
        return cls(
            id=data["id"],
            entity_id=data["entity_id"],
            action=data["action"],
            suggested_time=data["suggested_time"],
            time_window_start=data["time_window_start"],
            time_window_end=data["time_window_end"],
            consistency_score=data["consistency_score"],
            occurrence_count=data["occurrence_count"],
            last_occurrence=data["last_occurrence"],
        )


# -----------------------------------------------------------------------------
# Sync functions - testable without HA dependencies
# -----------------------------------------------------------------------------


def is_manual_action(entry: dict[str, Any]) -> bool:
    """Check if a logbook entry represents a manual user action.

    Args:
        entry: A logbook entry dictionary from Home Assistant.

    Returns:
        True if the action was triggered by a user manually, False otherwise.
    """
    # Must have a context_user_id to be user-triggered
    if not entry.get("context_user_id"):
        return False

    # Exclude automation-triggered actions
    if entry.get("context_event_type") == "automation_triggered":
        return False

    # Exclude internal/system events
    context_domain = entry.get("context_domain", "")
    if context_domain in ("automation", "script"):
        return False

    return True


def extract_action_from_entry(entry: dict[str, Any]) -> str:
    """Extract the action type from a logbook entry.

    Args:
        entry: A logbook entry dictionary from Home Assistant.

    Returns:
        A string representing the action type (e.g., "turn_on", "turn_off").
    """
    state = entry.get("state", "")

    # Handle different entity types
    entity_id = str(entry.get("entity_id") or "")
    domain = entity_id.split(".")[0] if "." in entity_id else ""

    if domain == "scene":
        return "activated"
    elif domain == "script":
        return "executed" if state == "on" else state
    elif domain in ("light", "switch", "cover", "input_boolean"):
        if state == "on":
            return "turn_on"
        elif state == "off":
            return "turn_off"
        else:
            return state
    elif domain == "climate":
        return f"set_{state}" if state else "changed"
    elif domain == "input_button":
        return "pressed"
    elif domain in ("input_number", "input_select", "input_datetime"):
        return "changed"
    else:
        return state or "unknown"


def parse_timestamp(ts_str: str | Any | None) -> datetime | None:
    """Parse ISO timestamp from Home Assistant.

    Args:
        ts_str: A timestamp string in ISO format, or None.

    Returns:
        A datetime object, or None if parsing fails.
    """
    if not ts_str:
        return None

    # Handle non-string inputs (e.g., integer timestamps)
    if not isinstance(ts_str, str):
        return None

    # Handle various timestamp formats
    ts_str = ts_str.replace("Z", "+00:00")

    try:
        # Try parsing with timezone
        if "+" in ts_str or ts_str.endswith("Z"):
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        else:
            return datetime.fromisoformat(ts_str)
    except ValueError:
        return None


def get_time_window(
    dt: datetime, window_minutes: int = DEFAULT_TIME_WINDOW_MINUTES
) -> str:
    """Get a time window string for grouping.

    Args:
        dt: A datetime object.
        window_minutes: Size of time window in minutes.

    Returns:
        A string in format "HH:MM" representing the window start.
    """
    hour = dt.hour
    minute_bucket = (dt.minute // window_minutes) * window_minutes
    return f"{hour:02d}:{minute_bucket:02d}"


def format_time_range(hours: list[int]) -> str:
    """Format a list of hours as a time range string.

    Args:
        hours: List of hour values (0-23).

    Returns:
        A formatted time range string like "07:00-09:59".
    """
    if not hours:
        return "unknown"

    min_hour = min(hours)
    max_hour = max(hours)

    if min_hour == max_hour:
        return f"{min_hour:02d}:00"
    else:
        return f"{min_hour:02d}:00-{max_hour:02d}:59"


def calculate_time_window_bounds(window: str, window_minutes: int = DEFAULT_TIME_WINDOW_MINUTES) -> tuple[str, str]:
    """Calculate start and end times for a time window.

    Args:
        window: Time window string in format "HH:MM".
        window_minutes: Size of time window in minutes.

    Returns:
        Tuple of (start_time, end_time) as "HH:MM" strings.
    """
    try:
        hour, minute = map(int, window.split(":"))
        start = f"{hour:02d}:{minute:02d}"
        end_minute = minute + window_minutes - 1
        end_hour = hour
        if end_minute >= 60:
            end_minute -= 60
            end_hour = (hour + 1) % 24
        end = f"{end_hour:02d}:{end_minute:02d}"
        return start, end
    except (ValueError, AttributeError):
        return "00:00", "00:29"


def calculate_suggested_time(window: str) -> str:
    """Calculate suggested trigger time from a time window.

    Rounds to the nearest 15 minutes within the window.

    Args:
        window: Time window string in format "HH:MM".

    Returns:
        Suggested trigger time as "HH:MM" string.
    """
    try:
        hour, minute = map(int, window.split(":"))
        suggested_minute = (minute // 15) * 15
        return f"{hour:02d}:{suggested_minute:02d}"
    except (ValueError, AttributeError):
        return "00:00"


def analyze_patterns(
    actions_by_entity: dict[str, dict[str, list[datetime | None]]],
    window_minutes: int = DEFAULT_TIME_WINDOW_MINUTES,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Analyze timing patterns in actions.

    Args:
        actions_by_entity: Nested dict of entity_id -> action -> list of timestamps.
        window_minutes: Size of time window for grouping in minutes.

    Returns:
        Nested dict of entity_id -> action -> pattern data.
    """
    patterns: dict[str, dict[str, dict[str, Any]]] = {}

    for entity_id, actions in actions_by_entity.items():
        entity_patterns: dict[str, dict[str, Any]] = {}

        for action_type, timestamps in actions.items():
            # Filter out None timestamps
            valid_timestamps = [ts for ts in timestamps if ts is not None]

            if len(valid_timestamps) < 2:
                continue

            # Group by time window
            time_windows: dict[str, list[datetime]] = defaultdict(list)
            hours: list[int] = []

            for ts in valid_timestamps:
                window = get_time_window(ts, window_minutes)
                time_windows[window].append(ts)
                hours.append(ts.hour)

            # Find the most common time window
            if time_windows:
                most_common_window = max(
                    time_windows.keys(), key=lambda w: len(time_windows[w])
                )
                window_count = len(time_windows[most_common_window])
                last_ts = max(valid_timestamps)

                entity_patterns[action_type] = {
                    "total_count": len(valid_timestamps),
                    "most_common_window": most_common_window,
                    "window_count": window_count,
                    "hours": hours,
                    "time_range": format_time_range(hours),
                    "last_timestamp": last_ts,
                    "timestamps_in_window": time_windows[most_common_window],
                }

        if entity_patterns:
            patterns[entity_id] = entity_patterns

    return patterns


def find_automation_candidates(
    patterns: dict[str, dict[str, dict[str, Any]]],
    min_occurrences: int = 3,
    consistency_threshold: float = 0.5,
) -> list[dict[str, Any]]:
    """Find actions that are good candidates for automation.

    Args:
        patterns: Pattern data from analyze_patterns().
        min_occurrences: Minimum total occurrences required.
        consistency_threshold: Minimum ratio of window_count/total_count.

    Returns:
        List of automation candidate dictionaries, sorted by consistency.
    """
    candidates: list[dict[str, Any]] = []

    for entity_id, entity_patterns in patterns.items():
        for action_type, pattern_data in entity_patterns.items():
            total = pattern_data["total_count"]
            window_count = pattern_data["window_count"]

            # Check if this meets the threshold for automation
            consistency = window_count / total if total > 0 else 0

            if total >= min_occurrences and consistency >= consistency_threshold:
                most_common_window = pattern_data["most_common_window"]
                last_ts = pattern_data.get("last_timestamp")

                candidates.append({
                    "entity_id": entity_id,
                    "action": action_type,
                    "total_occurrences": total,
                    "pattern_window": most_common_window,
                    "pattern_occurrences": window_count,
                    "time_range": pattern_data["time_range"],
                    "consistency": consistency,
                    "last_timestamp": last_ts,
                })

    # Sort by consistency and frequency
    candidates.sort(
        key=lambda c: (c["consistency"], c["total_occurrences"]), reverse=True
    )

    return candidates


def create_suggestion_from_candidate(
    candidate: dict[str, Any],
    window_minutes: int = DEFAULT_TIME_WINDOW_MINUTES,
) -> Suggestion:
    """Create a Suggestion object from a candidate dictionary.

    Args:
        candidate: Candidate data from find_automation_candidates().
        window_minutes: Size of time window in minutes.

    Returns:
        A Suggestion dataclass instance.
    """
    entity_id = candidate["entity_id"]
    action = candidate["action"]
    window = candidate["pattern_window"]

    # Create unique ID
    suggestion_id = f"{entity_id}_{action}_{window}".replace(".", "_").replace(":", "_")

    # Calculate time bounds
    time_start, time_end = calculate_time_window_bounds(window, window_minutes)

    # Calculate suggested trigger time
    suggested_time = calculate_suggested_time(window)

    # Format last occurrence
    last_ts = candidate.get("last_timestamp")
    last_occurrence = last_ts.isoformat() if last_ts else ""

    return Suggestion(
        id=suggestion_id,
        entity_id=entity_id,
        action=action,
        suggested_time=suggested_time,
        time_window_start=time_start,
        time_window_end=time_end,
        consistency_score=candidate["consistency"],
        occurrence_count=candidate["total_occurrences"],
        last_occurrence=last_occurrence,
    )


# -----------------------------------------------------------------------------
# Sync analysis function - can be called from executor
# -----------------------------------------------------------------------------


def analyze_logbook_entries(
    entries: list[dict[str, Any]],
    tracked_domains: list[str],
    min_occurrences: int,
    consistency_threshold: float,
    window_minutes: int = DEFAULT_TIME_WINDOW_MINUTES,
) -> list[Suggestion]:
    """Analyze logbook entries and return suggestions.

    This is a sync function that can be run in an executor.

    Args:
        entries: List of logbook entry dictionaries.
        tracked_domains: List of entity domains to track.
        min_occurrences: Minimum occurrences for a suggestion.
        consistency_threshold: Minimum consistency score (0-1).
        window_minutes: Size of time window in minutes.

    Returns:
        List of Suggestion objects.
    """
    # Collect manual actions by entity
    actions_by_entity: dict[str, dict[str, list[datetime | None]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for entry in entries:
        entity_id = str(entry.get("entity_id") or "")

        # Check if entity is in our target domains
        domain = entity_id.split(".")[0] if "." in entity_id else ""
        if domain not in tracked_domains:
            continue

        # Check if it's a manual action
        if not is_manual_action(entry):
            continue

        # Extract action and timestamp
        action = extract_action_from_entry(entry)
        timestamp = parse_timestamp(entry.get("when"))

        actions_by_entity[entity_id][action].append(timestamp)

    # Analyze patterns
    patterns = analyze_patterns(actions_by_entity, window_minutes)

    # Find automation candidates
    candidates = find_automation_candidates(
        patterns, min_occurrences, consistency_threshold
    )

    # Convert to Suggestion objects
    suggestions = [
        create_suggestion_from_candidate(c, window_minutes) for c in candidates
    ]

    return suggestions


# -----------------------------------------------------------------------------
# Fallback: State history analysis (limited context info)
# -----------------------------------------------------------------------------


async def _analyze_via_state_history(
    hass: "HomeAssistant",
    start_time: datetime,
    end_time: datetime,
    min_occurrences: int,
    consistency_threshold: float,
    dismissed_suggestions: set[str],
) -> list[Suggestion]:
    """Fallback analysis using state history (limited context info).

    This method uses get_significant_states which doesn't have context_user_id,
    so it treats ALL state changes as potential manual actions. Less accurate
    but works without API access.
    """
    from homeassistant.components.recorder import get_instance
    from homeassistant.components.recorder.history import get_significant_states

    # Get entity IDs for tracked domains
    tracked_entity_ids: list[str] = []
    for state in hass.states.async_all():
        domain = state.entity_id.split(".")[0]
        if domain in TRACKED_DOMAINS:
            tracked_entity_ids.append(state.entity_id)

    if not tracked_entity_ids:
        _LOGGER.debug("No entities found in tracked domains")
        return []

    try:
        states_by_entity = await get_instance(hass).async_add_executor_job(
            get_significant_states,
            hass,
            start_time,
            end_time,
            tracked_entity_ids,
            None,  # filters
            True,  # include_start_time_state
            True,  # significant_changes_only
            False,  # minimal_response
        )
    except Exception as err:
        _LOGGER.error("Error querying state history: %s", err)
        return []

    # Convert to entries - mark all as having context_user_id since we can't tell
    entries: list[dict[str, Any]] = []
    for entity_id, states in states_by_entity.items():
        for state in states:
            entry = {
                "entity_id": entity_id,
                "state": state.state,
                "when": state.last_changed.isoformat() if state.last_changed else None,
                "context_user_id": "unknown",  # Assume manual since we can't tell
                "context_event_type": None,
                "context_domain": None,
            }
            # If there's a parent context, mark as potentially automated
            if state.context and state.context.parent_id:
                entry["context_user_id"] = None  # Skip these
            entries.append(entry)

    _LOGGER.debug("Collected %d state entries for fallback analysis", len(entries))

    suggestions = await hass.async_add_executor_job(
        analyze_logbook_entries,
        entries,
        TRACKED_DOMAINS,
        min_occurrences,
        consistency_threshold,
        DEFAULT_TIME_WINDOW_MINUTES,
    )

    return [s for s in suggestions if s.id not in dismissed_suggestions]


# -----------------------------------------------------------------------------
# Async entry point for Home Assistant
# -----------------------------------------------------------------------------


async def analyze_patterns_async(
    hass: HomeAssistant,
    lookback_days: int,
    min_occurrences: int,
    consistency_threshold: float,
    dismissed_suggestions: set[str],
) -> list[Suggestion]:
    """Analyze patterns asynchronously using Home Assistant APIs.

    This is the main entry point for the integration to analyze patterns.
    It queries the logbook API for state changes with context information
    and identifies candidates for automation.

    Args:
        hass: Home Assistant instance.
        lookback_days: Number of days to look back for patterns.
        min_occurrences: Minimum occurrences to suggest automation.
        consistency_threshold: Minimum consistency score (0-1).
        dismissed_suggestions: Set of suggestion IDs to filter out.

    Returns:
        List of Suggestion objects, filtered to exclude dismissed ones.
    """
    from homeassistant.util import dt as dt_util
    from aiohttp import ClientSession

    end_time = dt_util.utcnow()
    start_time = end_time - timedelta(days=lookback_days)

    _LOGGER.debug(
        "Starting pattern analysis from %s to %s",
        start_time.isoformat(),
        end_time.isoformat(),
    )

    # Query logbook API which has context_user_id information
    # Use internal API endpoint
    try:
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        session = async_get_clientsession(hass)

        # Get the internal API URL
        base_url = f"http://127.0.0.1:{hass.http.server_port}"

        # Get a long-lived access token or use internal auth
        # For internal requests, we can use the supervisor token if available
        import os
        token = os.environ.get("SUPERVISOR_TOKEN")

        if not token:
            # Try to create a temporary token for internal use
            from homeassistant.auth.models import TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
            try:
                # Get the owner user
                owner = await hass.auth.async_get_owner()
                if owner:
                    # Create a refresh token and access token
                    refresh_token = await hass.auth.async_create_refresh_token(
                        owner,
                        client_name="Automation Suggestions Internal",
                        token_type=TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
                        access_token_expiration=timedelta(minutes=5),
                    )
                    token = hass.auth.async_create_access_token(refresh_token)
            except Exception as auth_err:
                _LOGGER.debug("Could not create internal token: %s", auth_err)

        if not token:
            _LOGGER.warning(
                "No authentication token available for logbook API. "
                "Falling back to state history (context info may be limited)."
            )
            return await _analyze_via_state_history(
                hass, start_time, end_time, min_occurrences,
                consistency_threshold, dismissed_suggestions
            )

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # Query logbook API
        start_str = start_time.isoformat()
        end_str = end_time.isoformat()
        url = f"{base_url}/api/logbook/{start_str}"
        params = {"end_time": end_str}

        async with session.get(url, headers=headers, params=params, timeout=60) as response:
            if response.status != 200:
                _LOGGER.error("Logbook API returned status %s", response.status)
                return []
            entries = await response.json()

    except Exception as err:
        _LOGGER.error("Error querying logbook API: %s", err)
        return []

    _LOGGER.debug("Retrieved %d logbook entries", len(entries))

    # Run the analysis in executor (CPU-bound work)
    suggestions = await hass.async_add_executor_job(
        analyze_logbook_entries,
        entries,
        TRACKED_DOMAINS,
        min_occurrences,
        consistency_threshold,
        DEFAULT_TIME_WINDOW_MINUTES,
    )

    # Filter out dismissed suggestions
    filtered_suggestions = [s for s in suggestions if s.id not in dismissed_suggestions]

    _LOGGER.info(
        "Pattern analysis complete: %d suggestions (%d after filtering dismissed)",
        len(suggestions),
        len(filtered_suggestions),
    )

    return filtered_suggestions
