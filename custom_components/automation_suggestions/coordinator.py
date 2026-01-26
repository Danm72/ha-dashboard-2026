"""Data update coordinator for the Automation Suggestions integration.

This coordinator manages scheduled pattern analysis and persistence
of dismissed suggestions.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .analyzer import StaleAutomation, Suggestion, analyze_patterns_async, find_stale_automations
from .const import (
    CONF_ANALYSIS_INTERVAL,
    CONF_CONSISTENCY_THRESHOLD,
    CONF_DOMAIN_FILTER_MODE,
    CONF_FILTERED_DOMAINS,
    CONF_FILTERED_USERS,
    CONF_IGNORE_AUTOMATION_PATTERNS,
    CONF_LOOKBACK_DAYS,
    CONF_MIN_OCCURRENCES,
    CONF_STALE_THRESHOLD_DAYS,
    CONF_USER_FILTER_MODE,
    DEFAULT_ANALYSIS_INTERVAL,
    DEFAULT_CONSISTENCY_THRESHOLD,
    DEFAULT_DOMAIN_FILTER_MODE,
    DEFAULT_EMOJI,
    DEFAULT_FILTERED_DOMAINS,
    DEFAULT_FILTERED_USERS,
    DEFAULT_IGNORE_AUTOMATION_PATTERNS,
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_MIN_OCCURRENCES,
    DEFAULT_STALE_THRESHOLD_DAYS,
    DEFAULT_USER_FILTER_MODE,
    DOMAIN,
    DOMAIN_EMOJI_MAP,
)

if TYPE_CHECKING:
    from typing import Any

_LOGGER = logging.getLogger(__name__)

# Storage version for schema migrations
STORAGE_VERSION = 2


class AutomationSuggestionsCoordinator(DataUpdateCoordinator[list[Suggestion]]):
    """Coordinator for automation suggestions pattern analysis.

    This coordinator:
    - Runs pattern analysis on a schedule (default weekly)
    - Persists dismissed suggestions to storage
    - Provides suggestion data to sensors
    """

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance.
            entry: Config entry with options for analysis parameters.
        """
        # Get analysis interval from options, falling back to data, then defaults
        analysis_interval_days = entry.options.get(
            CONF_ANALYSIS_INTERVAL,
            entry.data.get(CONF_ANALYSIS_INTERVAL, DEFAULT_ANALYSIS_INTERVAL),
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(days=analysis_interval_days),
        )

        self.config_entry = entry

        # Initialize storage for dismissed suggestions
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.persisted")
        self._dismissed: set[str] = set()
        self._stale_automations: list[StaleAutomation] = []
        self._dismissed_stale: set[str] = set()
        self._last_update_time: datetime | None = None

        # Cache config values
        self._lookback_days: int = entry.options.get(
            CONF_LOOKBACK_DAYS,
            entry.data.get(CONF_LOOKBACK_DAYS, DEFAULT_LOOKBACK_DAYS),
        )
        self._min_occurrences: int = entry.options.get(
            CONF_MIN_OCCURRENCES,
            entry.data.get(CONF_MIN_OCCURRENCES, DEFAULT_MIN_OCCURRENCES),
        )
        self._consistency_threshold: float = entry.options.get(
            CONF_CONSISTENCY_THRESHOLD,
            entry.data.get(CONF_CONSISTENCY_THRESHOLD, DEFAULT_CONSISTENCY_THRESHOLD),
        )

        # Cache filter config
        self._user_filter_mode: str = entry.options.get(
            CONF_USER_FILTER_MODE,
            entry.data.get(CONF_USER_FILTER_MODE, DEFAULT_USER_FILTER_MODE),
        )
        self._filtered_users: set[str] = set(
            entry.options.get(
                CONF_FILTERED_USERS,
                entry.data.get(CONF_FILTERED_USERS, DEFAULT_FILTERED_USERS),
            )
        )
        self._domain_filter_mode: str = entry.options.get(
            CONF_DOMAIN_FILTER_MODE,
            entry.data.get(CONF_DOMAIN_FILTER_MODE, DEFAULT_DOMAIN_FILTER_MODE),
        )
        self._filtered_domains: set[str] = set(
            entry.options.get(
                CONF_FILTERED_DOMAINS,
                entry.data.get(CONF_FILTERED_DOMAINS, DEFAULT_FILTERED_DOMAINS),
            )
        )

        # Cache stale detection config
        self._stale_threshold_days: int = entry.options.get(
            CONF_STALE_THRESHOLD_DAYS,
            entry.data.get(CONF_STALE_THRESHOLD_DAYS, DEFAULT_STALE_THRESHOLD_DAYS),
        )
        self._ignore_automation_patterns: list[str] = entry.options.get(
            CONF_IGNORE_AUTOMATION_PATTERNS,
            entry.data.get(CONF_IGNORE_AUTOMATION_PATTERNS, DEFAULT_IGNORE_AUTOMATION_PATTERNS),
        )

        _LOGGER.debug(
            "Coordinator initialized with interval=%d days, lookback=%d days, "
            "min_occurrences=%d, consistency=%.2f",
            analysis_interval_days,
            self._lookback_days,
            self._min_occurrences,
            self._consistency_threshold,
        )

    @property
    def dismissed(self) -> set[str]:
        """Return the set of dismissed suggestion IDs."""
        return self._dismissed

    @property
    def stale_automations(self) -> list[StaleAutomation]:
        """Return stale automations excluding dismissed."""
        return [s for s in self._stale_automations if s.automation_id not in self._dismissed_stale]

    async def async_load_persisted(self) -> None:
        """Load dismissed suggestions and stale automations from storage.

        Handles migration from storage v1 to v2.
        """
        try:
            stored_data = await self._store.async_load()
            if stored_data:
                # Load dismissed suggestions
                if "dismissed" in stored_data:
                    self._dismissed = set(stored_data["dismissed"])
                    _LOGGER.debug(
                        "Loaded %d dismissed suggestions from storage",
                        len(self._dismissed),
                    )
                else:
                    self._dismissed = set()

                # Load dismissed stale automations (v2+)
                if "dismissed_stale" in stored_data:
                    self._dismissed_stale = set(stored_data["dismissed_stale"])
                    _LOGGER.debug(
                        "Loaded %d dismissed stale automations from storage",
                        len(self._dismissed_stale),
                    )
                else:
                    self._dismissed_stale = set()
            else:
                self._dismissed = set()
                self._dismissed_stale = set()
                _LOGGER.debug("No persisted data found in storage")
        except Exception as err:
            _LOGGER.warning("Error loading persisted data: %s", err)
            self._dismissed = set()
            self._dismissed_stale = set()

    async def async_dismiss(self, item_id: str) -> None:
        """Dismiss a suggestion or stale automation and persist to storage.

        Args:
            item_id: The ID of the item to dismiss. If starts with 'automation.',
                     treats as stale automation; otherwise treats as suggestion.
        """
        if item_id.startswith("automation."):
            if item_id in self._dismissed_stale:
                _LOGGER.debug("Stale automation %s already dismissed", item_id)
                return
            self._dismissed_stale.add(item_id)
            _LOGGER.info("Dismissed stale automation: %s", item_id)
        else:
            if item_id in self._dismissed:
                _LOGGER.debug("Suggestion %s already dismissed", item_id)
                return
            self._dismissed.add(item_id)
            _LOGGER.info("Dismissed suggestion: %s", item_id)

        await self._async_save_persisted()
        await self.async_request_refresh()

    async def async_clear_dismissed(self) -> None:
        """Clear all dismissed suggestions and stale automations."""
        self._dismissed.clear()
        self._dismissed_stale.clear()
        await self._async_save_persisted()
        _LOGGER.info("Cleared all dismissed items")
        await self.async_request_refresh()

    async def _async_save_persisted(self) -> None:
        """Save dismissed suggestions and stale automations to storage."""
        try:
            await self._store.async_save(
                {
                    "dismissed": list(self._dismissed),
                    "dismissed_stale": list(self._dismissed_stale),
                }
            )
            _LOGGER.debug(
                "Saved %d dismissed suggestions and %d dismissed stale automations",
                len(self._dismissed),
                len(self._dismissed_stale),
            )
        except Exception as err:
            _LOGGER.error("Error saving persisted data: %s", err)

    async def _async_send_notifications(self, suggestions: list[Suggestion]) -> None:
        """Send a persistent notification with all suggestions grouped by domain.

        Sends notification on every analysis run with all current suggestions.
        Uses a fixed notification_id so new notifications replace previous ones.

        Args:
            suggestions: List of suggestions from pattern analysis.
        """
        if not suggestions:
            return

        _LOGGER.debug(
            "Sending notification for %d suggestions",
            len(suggestions),
        )

        # Group suggestions by domain
        by_domain: dict[str, list[Suggestion]] = defaultdict(list)
        for s in suggestions:
            # Defensive check for malformed entity_id
            if "." not in s.entity_id:
                _LOGGER.warning("Malformed entity_id: %s", s.entity_id)
                continue
            domain = s.entity_id.split(".")[0]
            by_domain[domain].append(s)

        # Build message with domain sections (sorted by count descending)
        sections = []
        for domain in sorted(by_domain.keys(), key=lambda d: -len(by_domain[d])):
            emoji = DOMAIN_EMOJI_MAP.get(domain, DEFAULT_EMOJI)
            count = len(by_domain[domain])
            domain_label = domain.replace("_", " ").title()
            header = f"## {emoji} {domain_label} ({count})"

            bullets = []
            for s in by_domain[domain]:
                name = s.friendly_name if s.friendly_name else s.entity_id
                action = s.format_action()
                pct = int(s.consistency_score * 100)
                bullets.append(
                    f"• {action} {name} around {s.suggested_time}\n"
                    f"  {pct}% consistent, seen {s.occurrence_count} times"
                )

            sections.append(header + "\n" + "\n".join(bullets))

        message = (
            "Based on your recent activity:\n\n"
            + "\n\n".join(sections)
            + "\n\nTo create these automations, go to Settings > Automations & Scenes."
        )

        try:
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "Automation Suggestions Found",
                    "message": message,
                    "notification_id": "automation_suggestions_batch",
                },
            )
            _LOGGER.debug("Sent notification for %d suggestions", len(suggestions))
        except Exception as err:
            _LOGGER.warning(
                "Failed to send notification: %s",
                err,
            )

    async def _async_update_data(self) -> list[Suggestion]:
        """Fetch and analyze patterns.

        This is called by the coordinator on the configured schedule.

        Returns:
            List of Suggestion objects representing automation candidates.

        Raises:
            UpdateFailed: If pattern analysis fails.
        """
        _LOGGER.debug(
            "Starting pattern analysis (lookback=%d days, min_occurrences=%d, " "consistency=%.2f)",
            self._lookback_days,
            self._min_occurrences,
            self._consistency_threshold,
        )

        try:
            suggestions = await analyze_patterns_async(
                self.hass,
                lookback_days=self._lookback_days,
                min_occurrences=self._min_occurrences,
                consistency_threshold=self._consistency_threshold,
                dismissed_suggestions=self._dismissed,
                excluded_users=self._filtered_users
                if self._user_filter_mode == "exclude"
                else None,
                included_users=self._filtered_users
                if self._user_filter_mode == "include"
                else None,
                excluded_domains=self._filtered_domains
                if self._domain_filter_mode == "exclude"
                else None,
                included_domains=self._filtered_domains
                if self._domain_filter_mode == "include"
                else None,
            )

            _LOGGER.info("Pattern analysis complete: found %d suggestions", len(suggestions))

            # Track the update time
            from homeassistant.util import dt as dt_util

            self._last_update_time = dt_util.utcnow()

            # Send notification with all suggestions
            await self._async_send_notifications(suggestions)

            # Detect stale automations
            try:
                automation_states = [
                    {
                        "entity_id": state.entity_id,
                        "state": state.state,
                        "attributes": dict(state.attributes),
                    }
                    for state in self.hass.states.async_all("automation")
                ]
                self._stale_automations = find_stale_automations(
                    automation_states,
                    self._stale_threshold_days,
                    self._ignore_automation_patterns,
                )
                _LOGGER.info(
                    "Found %d stale automations (threshold: %d days)",
                    len(self._stale_automations),
                    self._stale_threshold_days,
                )
            except Exception as err:
                _LOGGER.warning("Error detecting stale automations: %s", err)
                self._stale_automations = []

            return suggestions

        except Exception as err:
            _LOGGER.error("Pattern analysis failed: %s", err)
            raise UpdateFailed(f"Pattern analysis failed: {err}") from err

    def update_config(self, entry: ConfigEntry) -> None:
        """Update coordinator configuration from entry options.

        Called when options are changed via the options flow.

        Args:
            entry: Updated config entry.
        """
        # Update cached config values
        self._lookback_days = entry.options.get(
            CONF_LOOKBACK_DAYS,
            entry.data.get(CONF_LOOKBACK_DAYS, DEFAULT_LOOKBACK_DAYS),
        )
        self._min_occurrences = entry.options.get(
            CONF_MIN_OCCURRENCES,
            entry.data.get(CONF_MIN_OCCURRENCES, DEFAULT_MIN_OCCURRENCES),
        )
        self._consistency_threshold = entry.options.get(
            CONF_CONSISTENCY_THRESHOLD,
            entry.data.get(CONF_CONSISTENCY_THRESHOLD, DEFAULT_CONSISTENCY_THRESHOLD),
        )

        # Update filter config
        self._user_filter_mode = entry.options.get(
            CONF_USER_FILTER_MODE,
            entry.data.get(CONF_USER_FILTER_MODE, DEFAULT_USER_FILTER_MODE),
        )
        self._filtered_users = set(
            entry.options.get(
                CONF_FILTERED_USERS,
                entry.data.get(CONF_FILTERED_USERS, DEFAULT_FILTERED_USERS),
            )
        )
        self._domain_filter_mode = entry.options.get(
            CONF_DOMAIN_FILTER_MODE,
            entry.data.get(CONF_DOMAIN_FILTER_MODE, DEFAULT_DOMAIN_FILTER_MODE),
        )
        self._filtered_domains = set(
            entry.options.get(
                CONF_FILTERED_DOMAINS,
                entry.data.get(CONF_FILTERED_DOMAINS, DEFAULT_FILTERED_DOMAINS),
            )
        )

        # Update the polling interval
        analysis_interval_days = entry.options.get(
            CONF_ANALYSIS_INTERVAL,
            entry.data.get(CONF_ANALYSIS_INTERVAL, DEFAULT_ANALYSIS_INTERVAL),
        )
        self.update_interval = timedelta(days=analysis_interval_days)

        # Update stale detection config
        self._stale_threshold_days = entry.options.get(
            CONF_STALE_THRESHOLD_DAYS,
            entry.data.get(CONF_STALE_THRESHOLD_DAYS, DEFAULT_STALE_THRESHOLD_DAYS),
        )
        self._ignore_automation_patterns = entry.options.get(
            CONF_IGNORE_AUTOMATION_PATTERNS,
            entry.data.get(CONF_IGNORE_AUTOMATION_PATTERNS, DEFAULT_IGNORE_AUTOMATION_PATTERNS),
        )

        _LOGGER.debug(
            "Coordinator config updated: interval=%d days, lookback=%d days, "
            "min_occurrences=%d, consistency=%.2f",
            analysis_interval_days,
            self._lookback_days,
            self._min_occurrences,
            self._consistency_threshold,
        )
