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


# =============================================================================
# Domain Emoji Mapping Tests
# =============================================================================


class TestDomainEmojiMapping:
    """Tests for the domain emoji mapping constants."""

    def test_light_domain_has_emoji(self):
        """Light domain should have lightbulb emoji."""
        from custom_components.automation_suggestions.const import DOMAIN_EMOJI_MAP

        assert DOMAIN_EMOJI_MAP["light"] == "💡"

    def test_switch_domain_has_emoji(self):
        """Switch domain should have plug emoji."""
        from custom_components.automation_suggestions.const import DOMAIN_EMOJI_MAP

        assert DOMAIN_EMOJI_MAP["switch"] == "🔌"

    def test_cover_domain_has_emoji(self):
        """Cover domain should have door emoji."""
        from custom_components.automation_suggestions.const import DOMAIN_EMOJI_MAP

        assert DOMAIN_EMOJI_MAP["cover"] == "🚪"

    def test_climate_domain_has_emoji(self):
        """Climate domain should have thermometer emoji."""
        from custom_components.automation_suggestions.const import DOMAIN_EMOJI_MAP

        assert DOMAIN_EMOJI_MAP["climate"] == "🌡️"

    def test_scene_domain_has_emoji(self):
        """Scene domain should have clapper board emoji."""
        from custom_components.automation_suggestions.const import DOMAIN_EMOJI_MAP

        assert DOMAIN_EMOJI_MAP["scene"] == "🎬"

    def test_script_domain_has_emoji(self):
        """Script domain should have scroll emoji."""
        from custom_components.automation_suggestions.const import DOMAIN_EMOJI_MAP

        assert DOMAIN_EMOJI_MAP["script"] == "📜"

    def test_input_number_domain_has_emoji(self):
        """Input number domain should have gear emoji."""
        from custom_components.automation_suggestions.const import DOMAIN_EMOJI_MAP

        assert DOMAIN_EMOJI_MAP["input_number"] == "⚙️"

    def test_input_boolean_domain_has_emoji(self):
        """Input boolean domain should have gear emoji."""
        from custom_components.automation_suggestions.const import DOMAIN_EMOJI_MAP

        assert DOMAIN_EMOJI_MAP["input_boolean"] == "⚙️"

    def test_input_select_domain_has_emoji(self):
        """Input select domain should have gear emoji."""
        from custom_components.automation_suggestions.const import DOMAIN_EMOJI_MAP

        assert DOMAIN_EMOJI_MAP["input_select"] == "⚙️"

    def test_input_datetime_domain_has_emoji(self):
        """Input datetime domain should have gear emoji."""
        from custom_components.automation_suggestions.const import DOMAIN_EMOJI_MAP

        assert DOMAIN_EMOJI_MAP["input_datetime"] == "⚙️"

    def test_input_button_domain_has_emoji(self):
        """Input button domain should have gear emoji."""
        from custom_components.automation_suggestions.const import DOMAIN_EMOJI_MAP

        assert DOMAIN_EMOJI_MAP["input_button"] == "⚙️"

    def test_all_tracked_domains_have_emoji(self):
        """All tracked domains should have an emoji mapping."""
        from custom_components.automation_suggestions.const import (
            DOMAIN_EMOJI_MAP,
            TRACKED_DOMAINS,
        )

        for domain in TRACKED_DOMAINS:
            assert domain in DOMAIN_EMOJI_MAP, f"Missing emoji for {domain}"

    def test_default_emoji_exists(self):
        """DEFAULT_EMOJI should exist for fallback."""
        from custom_components.automation_suggestions.const import DEFAULT_EMOJI

        assert DEFAULT_EMOJI == "📋"

    def test_default_emoji_is_different_from_mapped(self):
        """DEFAULT_EMOJI should be distinct from all mapped emojis for clarity."""
        from custom_components.automation_suggestions.const import (
            DEFAULT_EMOJI,
            DOMAIN_EMOJI_MAP,
        )

        mapped_emojis = set(DOMAIN_EMOJI_MAP.values())
        assert (
            DEFAULT_EMOJI not in mapped_emojis
        ), "DEFAULT_EMOJI should be unique to indicate fallback usage"
