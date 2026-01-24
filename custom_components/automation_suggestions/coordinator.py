"""Data update coordinator for the Automation Suggestions integration.

This coordinator manages scheduled pattern analysis and persistence
of dismissed suggestions.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .analyzer import Suggestion, analyze_patterns_async
from .const import (
    CONF_ANALYSIS_INTERVAL,
    CONF_CONSISTENCY_THRESHOLD,
    CONF_DOMAIN_FILTER_MODE,
    CONF_FILTERED_DOMAINS,
    CONF_FILTERED_USERS,
    CONF_LOOKBACK_DAYS,
    CONF_MIN_OCCURRENCES,
    CONF_USER_FILTER_MODE,
    DEFAULT_ANALYSIS_INTERVAL,
    DEFAULT_CONSISTENCY_THRESHOLD,
    DEFAULT_DOMAIN_FILTER_MODE,
    DEFAULT_FILTERED_DOMAINS,
    DEFAULT_FILTERED_USERS,
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_MIN_OCCURRENCES,
    DEFAULT_USER_FILTER_MODE,
    DOMAIN,
)

if TYPE_CHECKING:
    from typing import Any

_LOGGER = logging.getLogger(__name__)

# Storage version for schema migrations
STORAGE_VERSION = 1


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

    async def async_load_persisted(self) -> None:
        """Load dismissed suggestions from storage.

        Should be called during integration setup before first refresh.
        """
        try:
            stored_data = await self._store.async_load()
            if stored_data:
                if "dismissed" in stored_data:
                    self._dismissed = set(stored_data["dismissed"])
                    _LOGGER.debug(
                        "Loaded %d dismissed suggestions from storage",
                        len(self._dismissed),
                    )
                else:
                    self._dismissed = set()
            else:
                self._dismissed = set()
                _LOGGER.debug("No persisted suggestions found in storage")
        except Exception as err:
            _LOGGER.warning("Error loading persisted suggestions: %s", err)
            self._dismissed = set()

    async def async_dismiss(self, suggestion_id: str) -> None:
        """Dismiss a suggestion and persist to storage.

        Args:
            suggestion_id: The ID of the suggestion to dismiss.
        """
        if suggestion_id in self._dismissed:
            _LOGGER.debug("Suggestion %s already dismissed", suggestion_id)
            return

        self._dismissed.add(suggestion_id)
        _LOGGER.info("Dismissed suggestion: %s", suggestion_id)

        # Persist to storage
        await self._async_save_persisted()

        # Trigger an update to refresh the sensor data
        # (removes the dismissed suggestion from the list)
        await self.async_request_refresh()

    async def async_clear_dismissed(self) -> None:
        """Clear all dismissed suggestions.

        This can be useful for testing or if a user wants to re-evaluate
        previously dismissed suggestions.
        """
        self._dismissed.clear()
        await self._async_save_persisted()
        _LOGGER.info("Cleared all dismissed suggestions")
        await self.async_request_refresh()

    async def _async_save_persisted(self) -> None:
        """Save dismissed suggestions to storage."""
        try:
            await self._store.async_save(
                {
                    "dismissed": list(self._dismissed),
                }
            )
            _LOGGER.debug(
                "Saved %d dismissed suggestions to storage",
                len(self._dismissed),
            )
        except Exception as err:
            _LOGGER.error("Error saving persisted suggestions: %s", err)

    async def _async_send_notifications(self, suggestions: list[Suggestion]) -> None:
        """Send a persistent notification with all suggestions.

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

        # Build formatted list of suggestions
        # Format: "• {action} {friendly_name} around {time}\n  {consistency}% consistent, seen {count} times"
        bullet_points = []
        for s in suggestions:
            name = s.friendly_name if s.friendly_name else s.entity_id
            consistency_pct = int(s.consistency_score * 100)
            bullet_points.append(
                f"\u2022 {s.action} {name} around {s.suggested_time}\n"
                f"  {consistency_pct}% consistent, seen {s.occurrence_count} times"
            )

        # Build the notification message
        message = (
            "Based on your recent activity, here are some automations you might want to create:\n\n"
            + "\n\n".join(bullet_points)
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

        _LOGGER.debug(
            "Coordinator config updated: interval=%d days, lookback=%d days, "
            "min_occurrences=%d, consistency=%.2f",
            analysis_interval_days,
            self._lookback_days,
            self._min_occurrences,
            self._consistency_threshold,
        )
