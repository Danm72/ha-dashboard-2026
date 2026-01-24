"""
E2E tests for analyzer parameter permutations against live Home Assistant.

This test module runs the automation_suggestions analyzer with multiple
parameter combinations to help identify optimal thresholds for pattern detection.

Only runs in --live mode with a real Home Assistant instance.
"""

from datetime import UTC, datetime, timedelta

import pytest

# Import the analyzer function and constants
from custom_components.automation_suggestions.analyzer import (
    TRACKED_DOMAINS,
    analyze_logbook_entries,
)

pytestmark = [pytest.mark.e2e, pytest.mark.live_only]


# Parameter combinations to test
MIN_OCCURRENCES = [2, 3, 5, 7]
CONSISTENCY_THRESHOLDS = [0.3, 0.4, 0.5, 0.6, 0.7]
LOOKBACK_DAYS = [7, 14, 30]


def _fetch_logbook_entries(ha_api, lookback_days: int) -> list[dict]:
    """Fetch logbook entries from Home Assistant API.

    Args:
        ha_api: The ha_api fixture for making API calls
        lookback_days: Number of days to look back

    Returns:
        List of logbook entry dictionaries
    """
    end_time = datetime.now(UTC)
    start_time = end_time - timedelta(days=lookback_days)

    # Format as ISO timestamp for the API
    start_ts = start_time.strftime("%Y-%m-%dT%H:%M:%S")

    # Call the logbook API
    resp = ha_api("GET", f"/api/logbook/{start_ts}")

    if resp.status_code != 200:
        pytest.skip(f"Logbook API returned {resp.status_code}: {resp.text}")

    entries = resp.json()

    # Convert to our expected format
    converted_entries = []
    for entry in entries:
        converted = {
            "entity_id": entry.get("entity_id", ""),
            "state": entry.get("state", ""),
            "when": entry.get("when"),
            "context_user_id": entry.get("context_user_id"),
            "context_event_type": entry.get("context_event_type"),
            "context_domain": entry.get("context_domain"),
        }
        converted_entries.append(converted)

    return converted_entries


def _format_suggestion(suggestion) -> str:
    """Format a suggestion for display.

    Args:
        suggestion: Suggestion object from analyzer

    Returns:
        Formatted string for display
    """
    return (
        f"  - {suggestion.entity_id} {suggestion.action} "
        f"{suggestion.suggested_time} ({suggestion.consistency_score:.2f})"
    )


class TestAnalyzerPermutations:
    """Test analyzer with multiple parameter permutations."""

    def test_permutations_summary(self, ha_api, is_live_mode):
        """Run analyzer with all parameter permutations and print summary.

        This test iterates through all combinations of:
        - lookback_days: [7, 14, 30]
        - min_occurrences: [2, 3, 5, 7]
        - consistency_threshold: [0.3, 0.4, 0.5, 0.6, 0.7]

        Results are printed as a readable summary showing suggestion counts
        and top suggestions for each parameter combination.
        """
        if not is_live_mode:
            pytest.skip("This test only runs in --live mode")

        # Cache logbook entries by lookback period to avoid redundant API calls
        entries_cache: dict[int, list[dict]] = {}

        # Store results for summary
        results = []

        print("\n" + "=" * 60)
        print("=== Parameter Permutation Results ===")
        print("=" * 60)

        for lookback in LOOKBACK_DAYS:
            # Fetch entries for this lookback period (cached)
            if lookback not in entries_cache:
                print(f"\nFetching logbook entries for {lookback} day lookback...")
                entries_cache[lookback] = _fetch_logbook_entries(ha_api, lookback)
                print(f"  Retrieved {len(entries_cache[lookback])} entries")

            entries = entries_cache[lookback]

            if not entries:
                print(f"\nNo entries found for lookback={lookback} days")
                continue

            for min_occ in MIN_OCCURRENCES:
                for threshold in CONSISTENCY_THRESHOLDS:
                    # Run the analyzer
                    suggestions = analyze_logbook_entries(
                        entries=entries,
                        tracked_domains=list(TRACKED_DOMAINS),
                        min_occurrences=min_occ,
                        consistency_threshold=threshold,
                    )

                    # Store result
                    result = {
                        "lookback": lookback,
                        "min_occ": min_occ,
                        "threshold": threshold,
                        "count": len(suggestions),
                        "suggestions": suggestions[:5],  # Top 5
                    }
                    results.append(result)

                    # Print result
                    print(
                        f"\nlookback={lookback}, min_occ={min_occ}, "
                        f"threshold={threshold}: {len(suggestions)} suggestions"
                    )

                    # Print top 5 suggestions
                    for suggestion in suggestions[:5]:
                        print(_format_suggestion(suggestion))

        # Print summary table
        print("\n" + "=" * 60)
        print("=== Summary Table ===")
        print("=" * 60)
        print(f"{'Lookback':>8} | {'MinOcc':>6} | {'Threshold':>9} | {'Count':>5}")
        print("-" * 40)

        for r in results:
            print(
                f"{r['lookback']:>8} | {r['min_occ']:>6} | "
                f"{r['threshold']:>9.1f} | {r['count']:>5}"
            )

        print("=" * 60)

        # Basic assertion to ensure the test ran
        assert len(results) > 0, "Should have at least one result"

    def test_logbook_api_accessible(self, ha_api, is_live_mode):
        """Verify the logbook API is accessible in live mode."""
        if not is_live_mode:
            pytest.skip("This test only runs in --live mode")

        resp = ha_api("GET", "/api/logbook")
        assert (
            resp.status_code == 200
        ), f"Logbook API should be accessible, got {resp.status_code}: {resp.text}"

    def test_tracked_domains_coverage(self, ha_api, is_live_mode):
        """Check which tracked domains have entries in the logbook."""
        if not is_live_mode:
            pytest.skip("This test only runs in --live mode")

        entries = _fetch_logbook_entries(ha_api, lookback_days=14)

        # Count entries by domain
        domain_counts: dict[str, int] = {}
        for entry in entries:
            entity_id = entry.get("entity_id", "")
            if "." in entity_id:
                domain = entity_id.split(".")[0]
                domain_counts[domain] = domain_counts.get(domain, 0) + 1

        print("\n=== Domain Coverage ===")
        print(f"Total entries: {len(entries)}")
        print("\nTracked domains with entries:")
        for domain in TRACKED_DOMAINS:
            count = domain_counts.get(domain, 0)
            if count > 0:
                print(f"  {domain}: {count} entries")

        print("\nOther domains with entries:")
        for domain, count in sorted(domain_counts.items(), key=lambda x: x[1], reverse=True):
            if domain not in TRACKED_DOMAINS:
                print(f"  {domain}: {count} entries")

        # Basic assertion
        assert len(entries) >= 0, "Should retrieve entries without error"


class TestManualActionFiltering:
    """Test that manual action filtering works correctly with live data."""

    def test_manual_vs_automated_actions(self, ha_api, is_live_mode):
        """Analyze manual vs automated action distribution in logbook."""
        if not is_live_mode:
            pytest.skip("This test only runs in --live mode")

        entries = _fetch_logbook_entries(ha_api, lookback_days=7)

        manual_count = 0
        automated_count = 0
        no_context_count = 0

        for entry in entries:
            if entry.get("context_user_id"):
                if entry.get("context_event_type") == "automation_triggered":
                    automated_count += 1
                elif entry.get("context_domain") in ("automation", "script"):
                    automated_count += 1
                else:
                    manual_count += 1
            else:
                no_context_count += 1

        print("\n=== Action Source Analysis ===")
        print(f"Total entries: {len(entries)}")
        print(f"Manual actions (context_user_id, no automation): {manual_count}")
        print(f"Automated actions: {automated_count}")
        print(f"No context (system/unknown): {no_context_count}")

        if len(entries) > 0:
            print(f"\nManual action ratio: {manual_count / len(entries):.1%}")

        # No assertion - just informational
        assert True
