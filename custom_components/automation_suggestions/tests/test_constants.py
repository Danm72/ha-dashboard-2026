"""Shared test constants and factory methods."""

from dataclasses import dataclass


@dataclass
class TestDataFactory:
    """Factory for creating test data."""

    @staticmethod
    def logbook_entry(
        entity_id: str = "light.living_room",
        state: str = "on",
        when: str = "2026-01-20T10:00:00Z",
        context_user_id: str | None = "user123",
        context_event_type: str | None = None,
        context_domain: str | None = None,
    ) -> dict:
        """Create a logbook entry for testing."""
        entry = {
            "entity_id": entity_id,
            "state": state,
            "when": when,
        }
        if context_user_id is not None:
            entry["context_user_id"] = context_user_id
        if context_event_type is not None:
            entry["context_event_type"] = context_event_type
        if context_domain is not None:
            entry["context_domain"] = context_domain
        return entry

    @staticmethod
    def suggestion(
        entity_id: str = "light.kitchen",
        action: str = "turn_on",
        suggested_time: str = "07:00",
        time_window_start: str = "06:45",
        time_window_end: str = "07:15",
        consistency_score: float = 0.85,
        occurrence_count: int = 10,
        last_occurrence: str = "2026-01-20T07:05:00+00:00",
    ) -> dict:
        """Create a suggestion dict for testing."""
        return {
            "id": f"{entity_id.replace('.', '_')}_{action}_{suggested_time.replace(':', '_')}",
            "entity_id": entity_id,
            "action": action,
            "suggested_time": suggested_time,
            "time_window_start": time_window_start,
            "time_window_end": time_window_end,
            "consistency_score": consistency_score,
            "occurrence_count": occurrence_count,
            "last_occurrence": last_occurrence,
        }


# Common test tokens
TEST_HA_TOKEN = "test_ha_token_12345"
TEST_USER_ID = "user_abc123"
