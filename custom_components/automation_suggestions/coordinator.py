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
    CONF_LOOKBACK_DAYS,
    CONF_MIN_OCCURRENCES,
    DEFAULT_ANALYSIS_INTERVAL,
    DEFAULT_CONSISTENCY_THRESHOLD,
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_MIN_OCCURRENCES,
    DOMAIN,
    HIGH_CONFIDENCE_THRESHOLD,
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

        # Initialize storage for dismissed and notified suggestions
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.persisted")
        self._dismissed: set[str] = set()
        self._notified: set[str] = set()
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
    def notified(self) -> set[str]:
        """Return the set of notified suggestion IDs."""
        return self._notified

    async def async_load_persisted(self) -> None:
        """Load dismissed and notified suggestions from storage.

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

                if "notified" in stored_data:
                    self._notified = set(stored_data["notified"])
                    _LOGGER.debug(
                        "Loaded %d notified suggestions from storage",
                        len(self._notified),
                    )
                else:
                    self._notified = set()
            else:
                self._dismissed = set()
                self._notified = set()
                _LOGGER.debug("No persisted suggestions found in storage")
        except Exception as err:
            _LOGGER.warning("Error loading persisted suggestions: %s", err)
            self._dismissed = set()
            self._notified = set()

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
        """Save dismissed and notified suggestions to storage."""
        try:
            await self._store.async_save(
                {
                    "dismissed": list(self._dismissed),
                    "notified": list(self._notified),
                }
            )
            _LOGGER.debug(
                "Saved %d dismissed and %d notified suggestions to storage",
                len(self._dismissed),
                len(self._notified),
            )
        except Exception as err:
            _LOGGER.error("Error saving persisted suggestions: %s", err)

    async def _async_send_notifications(self, suggestions: list[Suggestion]) -> None:
        """Send a batched persistent notification for new high-confidence suggestions.

        Only notifies for suggestions that:
        - Have consistency >= HIGH_CONFIDENCE_THRESHOLD (80%)
        - Haven't been notified before

        All new suggestions are batched into a single notification to avoid spam.

        Args:
            suggestions: List of suggestions from pattern analysis.
        """
        new_high_confidence = [
            s
            for s in suggestions
            if s.consistency_score >= HIGH_CONFIDENCE_THRESHOLD and s.id not in self._notified
        ]

        if not new_high_confidence:
            return

        _LOGGER.debug(
            "Found %d new high-confidence suggestions to notify",
            len(new_high_confidence),
        )

        # Build bulleted list of suggestions using description property
        # (description already uses friendly_name when available)
        bullet_points = [f"- {s.description}" for s in new_high_confidence]

        # Build the batched notification message
        count = len(new_high_confidence)
        suggestion_word = "pattern" if count == 1 else "patterns"
        message = (
            f"Found {count} {suggestion_word} you might want to automate:\n\n"
            + "\n".join(bullet_points)
            + "\n\nView all suggestions in the Automation Suggestions sensor."
        )

        try:
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "New Automation Suggestions Available",
                    "message": message,
                    "notification_id": "automation_suggestions_batch",
                },
            )
            # Mark all as notified
            for suggestion in new_high_confidence:
                self._notified.add(suggestion.id)
            _LOGGER.debug("Sent batched notification for %d suggestions", len(new_high_confidence))
        except Exception as err:
            _LOGGER.warning(
                "Failed to send batched notification: %s",
                err,
            )

        # Persist the updated notified set
        await self._async_save_persisted()

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
            )

            _LOGGER.info("Pattern analysis complete: found %d suggestions", len(suggestions))

            # Track the update time
            from homeassistant.util import dt as dt_util

            self._last_update_time = dt_util.utcnow()

            # Send notifications for new high-confidence suggestions
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
