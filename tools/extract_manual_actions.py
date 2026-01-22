#!/usr/bin/env python3.11
"""
extract_manual_actions.py - Query Home Assistant for manual user actions

Analyzes the logbook to find user-triggered actions and suggests automation candidates
based on patterns in timing and frequency.
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import requests


def get_ha_token():
    """Get Home Assistant token from env var or file."""
    token = os.environ.get("HA_TOKEN")
    if token:
        return token

    token_file = Path.home() / ".ha_token"
    if token_file.exists():
        return token_file.read_text().strip()

    raise ValueError(
        "No Home Assistant token found. "
        "Set HA_TOKEN environment variable or create ~/.ha_token file."
    )


def get_logbook_entries(base_url, token, start_time, end_time, entity_id=None):
    """Query the Home Assistant logbook API."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Format timestamps for API
    start_str = start_time.isoformat()
    end_str = end_time.isoformat()

    url = f"{base_url}/api/logbook/{start_str}"
    params = {"end_time": end_str}

    if entity_id:
        params["entity"] = entity_id

    response = requests.get(url, headers=headers, params=params, timeout=60)
    response.raise_for_status()

    return response.json()


def is_manual_action(entry):
    """Check if a logbook entry represents a manual user action."""
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


def extract_action_from_entry(entry):
    """Extract the action type from a logbook entry."""
    state = entry.get("state", "")

    # Handle different entity types
    entity_id = str(entry.get("entity_id") or "")
    domain = entity_id.split(".")[0] if "." in entity_id else ""

    if domain == "scene":
        return "activated"
    elif domain == "script":
        return "executed" if state == "on" else state
    elif domain in ("light", "switch", "cover"):
        if state == "on":
            return "turn_on"
        elif state == "off":
            return "turn_off"
        else:
            return state
    elif domain == "climate":
        return f"set_{state}" if state else "changed"
    else:
        return state or "unknown"


def parse_timestamp(ts_str):
    """Parse ISO timestamp from Home Assistant."""
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


def get_hour_bucket(dt):
    """Get the hour bucket (0-23) for a datetime."""
    return dt.hour


def get_time_window(dt, window_minutes=30):
    """Get a time window string for grouping."""
    hour = dt.hour
    minute_bucket = (dt.minute // window_minutes) * window_minutes
    return f"{hour:02d}:{minute_bucket:02d}"


def format_time_range(hours):
    """Format a list of hours as a time range string."""
    if not hours:
        return "unknown"

    min_hour = min(hours)
    max_hour = max(hours)

    if min_hour == max_hour:
        return f"{min_hour:02d}:00"
    else:
        return f"{min_hour:02d}:00-{max_hour:02d}:59"


def analyze_patterns(actions_by_entity):
    """Analyze timing patterns in actions."""
    patterns = {}

    for entity_id, actions in actions_by_entity.items():
        entity_patterns = {}

        for action_type, timestamps in actions.items():
            if len(timestamps) < 2:
                continue

            # Group by time window
            time_windows = defaultdict(list)
            hours = []

            for ts in timestamps:
                if ts:
                    window = get_time_window(ts)
                    time_windows[window].append(ts)
                    hours.append(ts.hour)

            # Find the most common time window
            if time_windows:
                most_common_window = max(time_windows.keys(), key=lambda w: len(time_windows[w]))
                window_count = len(time_windows[most_common_window])

                entity_patterns[action_type] = {
                    "total_count": len(timestamps),
                    "most_common_window": most_common_window,
                    "window_count": window_count,
                    "hours": hours,
                    "time_range": format_time_range(hours),
                }

        if entity_patterns:
            patterns[entity_id] = entity_patterns

    return patterns


def find_automation_candidates(patterns, min_occurrences=3):
    """Find actions that are good candidates for automation."""
    candidates = []

    for entity_id, entity_patterns in patterns.items():
        for action_type, pattern_data in entity_patterns.items():
            total = pattern_data["total_count"]
            window_count = pattern_data["window_count"]

            # Check if this meets the threshold for automation
            if total >= min_occurrences and window_count >= min_occurrences * 0.5:
                # Calculate consistency score
                consistency = window_count / total

                candidates.append({
                    "entity_id": entity_id,
                    "action": action_type,
                    "total_occurrences": total,
                    "pattern_window": pattern_data["most_common_window"],
                    "pattern_occurrences": window_count,
                    "time_range": pattern_data["time_range"],
                    "consistency": consistency,
                })

    # Sort by consistency and frequency
    candidates.sort(key=lambda c: (c["consistency"], c["total_occurrences"]), reverse=True)

    return candidates


def print_summary(actions_by_entity, patterns, days):
    """Print the manual actions summary."""
    print(f"\n=== Manual Actions Summary (Last {days} Days) ===\n")

    if not actions_by_entity:
        print("No manual actions found for the specified period.")
        return

    # Sort entities by total action count
    entity_totals = []
    for entity_id, actions in actions_by_entity.items():
        total = sum(len(ts_list) for ts_list in actions.values())
        entity_totals.append((entity_id, total, actions))

    entity_totals.sort(key=lambda x: x[1], reverse=True)

    for entity_id, total, actions in entity_totals:
        print(f"Entity: {entity_id}")
        print(f"  Actions: {total} total")

        entity_pattern = patterns.get(entity_id, {})

        for action_type, timestamps in sorted(actions.items(), key=lambda x: len(x[1]), reverse=True):
            count = len(timestamps)
            pattern_info = entity_pattern.get(action_type, {})
            time_range = pattern_info.get("time_range", "various times")

            print(f"  - {action_type}: {count} times (mostly {time_range})")

        print()


def print_automation_candidates(candidates):
    """Print automation candidate suggestions."""
    print("=== Automation Candidates ===\n")

    if not candidates:
        print("No clear automation candidates found.")
        print("Actions need to occur 3+ times with consistent timing to be suggested.")
        return

    for i, candidate in enumerate(candidates, 1):
        entity_id = candidate["entity_id"]
        action = candidate["action"]
        total = candidate["total_occurrences"]
        pattern_time = candidate["pattern_window"]
        pattern_count = candidate["pattern_occurrences"]
        consistency = candidate["consistency"]

        print(f"{i}. {entity_id} {action}")
        print(f"   Pattern: {pattern_count} of {total} occurrences around {pattern_time}")
        print(f"   Consistency: {consistency:.0%}")

        # Suggest trigger time (round to nearest 15 minutes)
        hour, minute = map(int, pattern_time.split(":"))
        suggested_minute = (minute // 15) * 15

        print(f"   Suggestion: Create automation for {hour:02d}:{suggested_minute:02d} trigger")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Extract manual user actions from Home Assistant logbook"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to look back (default: 7)"
    )
    parser.add_argument(
        "--base-url",
        default="http://192.168.1.217:8123",
        help="Home Assistant base URL (default: http://192.168.1.217:8123)"
    )
    parser.add_argument(
        "--min-occurrences",
        type=int,
        default=3,
        help="Minimum occurrences to suggest automation (default: 3)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format"
    )

    args = parser.parse_args()

    # Get token
    try:
        token = get_ha_token()
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Define domains to query
    domains = ["light", "switch", "scene", "cover", "climate", "script"]

    # Calculate time range
    end_time = datetime.now()
    start_time = end_time - timedelta(days=args.days)

    print(f"Querying Home Assistant at {args.base_url}")
    print(f"Time range: {start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}")
    print(f"Domains: {', '.join(domains)}")
    print("Fetching logbook entries...")

    # Collect all manual actions
    actions_by_entity = defaultdict(lambda: defaultdict(list))
    total_entries = 0
    manual_entries = 0

    try:
        # Query logbook
        entries = get_logbook_entries(args.base_url, token, start_time, end_time)
        total_entries = len(entries)

        for entry in entries:
            entity_id = str(entry.get("entity_id") or "")

            # Check if entity is in our target domains
            domain = entity_id.split(".")[0] if "." in entity_id else ""
            if domain not in domains:
                continue

            # Check if it's a manual action
            if not is_manual_action(entry):
                continue

            manual_entries += 1

            # Extract action and timestamp
            action = extract_action_from_entry(entry)
            timestamp = parse_timestamp(entry.get("when"))

            actions_by_entity[entity_id][action].append(timestamp)

        print(f"Found {total_entries} total logbook entries")
        print(f"Identified {manual_entries} manual actions across {len(actions_by_entity)} entities")

    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to Home Assistant at {args.base_url}", file=sys.stderr)
        return 1
    except requests.exceptions.HTTPError as e:
        print(f"Error: HTTP error from Home Assistant: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Analyze patterns
    patterns = analyze_patterns(actions_by_entity)

    # Find automation candidates
    candidates = find_automation_candidates(patterns, args.min_occurrences)

    # Output results
    if args.json:
        output = {
            "summary": {
                "days": args.days,
                "total_entries": total_entries,
                "manual_entries": manual_entries,
                "entities_with_actions": len(actions_by_entity),
            },
            "actions_by_entity": {
                entity_id: {
                    action: len(timestamps)
                    for action, timestamps in actions.items()
                }
                for entity_id, actions in actions_by_entity.items()
            },
            "patterns": patterns,
            "automation_candidates": candidates,
        }
        print(json.dumps(output, indent=2, default=str))
    else:
        print_summary(actions_by_entity, patterns, args.days)
        print_automation_candidates(candidates)

    return 0


if __name__ == "__main__":
    sys.exit(main())
