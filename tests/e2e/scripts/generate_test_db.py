#!/usr/bin/env python3
"""
Generate test recorder database with patterns for automation_suggestions analyzer.

This creates a home-assistant_v2.db with historical state data that contains:

HAPPY PATH (should be detected as automation candidates):
- Kitchen light turned on around 7:00 AM every day for 14 days
- Kitchen light turned off around 8:30 AM every day for 14 days
- Bedroom light turned off around 10:30 PM every day for 14 days
- Coffee maker turned on around 6:45 AM on weekdays for 14 days

UNHAPPY PATH (should be FILTERED OUT by the analyzer):
- Porch light: automation-triggered events (has context_parent_id)
- Morning routine switch: script-triggered events (has context_parent_id)
- Temperature sensor: system events without user context
- Garage light: random/inconsistent timing (below consistency threshold)

USER FILTERING PATTERNS (for testing user_filter_mode):
- Guest room light: events from a different user ID (e2e_guest_user_id_9999999999)

DOMAIN FILTERING PATTERNS (for testing domain_filter_mode):
- Automated light: events with context_domain="nodered"

Run this script to regenerate the test database:
    python tests/e2e/scripts/generate_test_db.py
"""

import json
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

# Output path
DB_PATH = Path(__file__).parent.parent / "initial_test_state" / "home-assistant_v2.db"

# ============================================================================
# HAPPY PATH PATTERNS - Manual user actions with consistent timing
# These SHOULD be detected as automation candidates
# ============================================================================
PATTERNS = [
    {
        "entity_id": "light.kitchen",
        "state": "on",
        "base_time": "07:00:00",
        "variance_minutes": 15,
        "days": 14,
        "weekdays_only": False,
    },
    {
        "entity_id": "light.kitchen",
        "state": "off",
        "base_time": "08:30:00",
        "variance_minutes": 20,
        "days": 14,
        "weekdays_only": False,
    },
    {
        "entity_id": "light.bedroom",
        "state": "off",
        "base_time": "22:30:00",
        "variance_minutes": 15,
        "days": 14,
        "weekdays_only": False,
    },
    {
        "entity_id": "switch.coffee_maker",
        "state": "on",
        "base_time": "06:45:00",
        "variance_minutes": 10,
        "days": 14,
        "weekdays_only": True,
    },
]

# ============================================================================
# UNHAPPY PATH PATTERNS - Events that should be FILTERED OUT
# ============================================================================

# Automation-triggered events - have context_parent_id set (indicates automation chain)
# These simulate a sunset automation turning on the porch light
AUTOMATION_TRIGGERED_PATTERNS = [
    {
        "entity_id": "light.porch",
        "state": "on",
        "base_time": "18:00:00",  # ~sunset time
        "variance_minutes": 30,  # Sunset varies
        "days": 14,
        "weekdays_only": False,
        "context_parent_id": "automation_sunset_001",  # Has parent = automation triggered
        "context_user_id": None,  # No user involved
    },
]

# Script-triggered events - have context_parent_id set
# These simulate a morning routine script
SCRIPT_TRIGGERED_PATTERNS = [
    {
        "entity_id": "switch.morning_routine",
        "state": "on",
        "base_time": "06:30:00",
        "variance_minutes": 5,
        "days": 14,
        "weekdays_only": True,
        "context_parent_id": "script_morning_routine_001",  # Has parent = script triggered
        "context_user_id": None,  # No user involved
    },
]

# System events without user context - no context_user_id
# These simulate sensor updates from integrations
SYSTEM_EVENT_PATTERNS = [
    {
        "entity_id": "sensor.temperature",
        "state_values": ["20.5", "21.0", "21.5", "22.0", "22.5", "23.0"],  # Varying states
        "hours_between": 1,  # Every hour
        "days": 14,
        "context_user_id": None,  # No user
        "context_parent_id": None,  # No parent
    },
]

# Random/inconsistent events - manual but no consistent pattern
# These should fail the consistency threshold even though they're manual
INCONSISTENT_PATTERNS = [
    {
        "entity_id": "light.garage",
        "state": "on",
        "days": 14,
        "events_per_day": 2,  # Random times throughout the day
        "context_user_id": "e2e_test_user_id_1234567890",  # Manual action
        "context_parent_id": None,
    },
]

# Guest user events - can be filtered with user_filter_mode="exclude"
GUEST_USER_PATTERNS = [
    {
        "entity_id": "light.guest_room",
        "state": "on",
        "base_time": "09:00:00",
        "variance_minutes": 15,
        "days": 14,
        "weekdays_only": False,
        "context_user_id": "e2e_guest_user_id_9999999999",  # Different user
        "context_parent_id": None,
    },
]

# Node-RED events - can be filtered with domain_filter_mode="exclude"
NODERED_DOMAIN_PATTERNS = [
    {
        "entity_id": "light.automated_light",
        "state": "on",
        "base_time": "19:00:00",
        "variance_minutes": 10,
        "days": 14,
        "weekdays_only": False,
        "context_user_id": "e2e_test_user_id_1234567890",  # Has user ID
        "context_parent_id": None,  # No parent (not automation triggered)
        "context_domain": "nodered",  # But triggered by Node-RED
    },
]


def create_schema(conn):
    """Create the recorder database schema."""
    cursor = conn.cursor()

    # States table (simplified schema matching HA recorder)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS states (
            state_id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id VARCHAR(255),
            state VARCHAR(255),
            attributes TEXT,
            last_changed DATETIME,
            last_updated DATETIME,
            context_id VARCHAR(36),
            context_user_id VARCHAR(36),
            context_parent_id VARCHAR(36),
            context_domain VARCHAR(64)
        )
    """)

    # States meta table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS states_meta (
            metadata_id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id VARCHAR(255) UNIQUE
        )
    """)

    # Events table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type VARCHAR(64),
            event_data TEXT,
            time_fired DATETIME,
            context_id VARCHAR(36),
            context_user_id VARCHAR(36),
            context_parent_id VARCHAR(36)
        )
    """)

    # Schema version
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_changes (
            change_id INTEGER PRIMARY KEY AUTOINCREMENT,
            schema_version INTEGER,
            changed DATETIME
        )
    """)
    cursor.execute("""
        INSERT INTO schema_changes (schema_version, changed) VALUES (43, datetime('now'))
    """)

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_states_entity_id ON states (entity_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_states_last_updated ON states (last_updated)")

    conn.commit()


def generate_state_changes(pattern, base_date):
    """Generate state changes for a happy path pattern (manual user action)."""
    states = []

    base_hour, base_minute, base_second = map(int, pattern["base_time"].split(":"))
    variance = pattern["variance_minutes"]

    for day_offset in range(pattern["days"]):
        day = base_date - timedelta(days=day_offset)

        # Skip weekends if weekdays_only
        if pattern["weekdays_only"] and day.weekday() >= 5:
            continue

        # Add random variance to time
        minute_offset = random.randint(-variance, variance)
        event_time = day.replace(
            hour=base_hour,
            minute=max(0, min(59, base_minute + minute_offset)),
            second=random.randint(0, 59),
            microsecond=0,
        )

        states.append(
            {
                "entity_id": pattern["entity_id"],
                "state": pattern["state"],
                "attributes": json.dumps(
                    {"friendly_name": pattern["entity_id"].split(".")[1].replace("_", " ").title()}
                ),
                "last_changed": event_time.isoformat(),
                "last_updated": event_time.isoformat(),
                "context_id": f"ctx_{day_offset}_{pattern['entity_id']}",
                "context_user_id": pattern.get(
                    "context_user_id", "e2e_test_user_id_1234567890"
                ),  # User-initiated
                "context_parent_id": pattern.get("context_parent_id"),
                "context_domain": pattern.get("context_domain"),
            }
        )

    return states


def generate_automation_triggered_events(pattern, base_date):
    """Generate automation-triggered events (should be filtered out)."""
    states = []

    base_hour, base_minute, _ = map(int, pattern["base_time"].split(":"))
    variance = pattern["variance_minutes"]

    for day_offset in range(pattern["days"]):
        day = base_date - timedelta(days=day_offset)

        if pattern["weekdays_only"] and day.weekday() >= 5:
            continue

        minute_offset = random.randint(-variance, variance)
        event_time = day.replace(
            hour=base_hour,
            minute=max(0, min(59, base_minute + minute_offset)),
            second=random.randint(0, 59),
            microsecond=0,
        )

        states.append(
            {
                "entity_id": pattern["entity_id"],
                "state": pattern["state"],
                "attributes": json.dumps(
                    {"friendly_name": pattern["entity_id"].split(".")[1].replace("_", " ").title()}
                ),
                "last_changed": event_time.isoformat(),
                "last_updated": event_time.isoformat(),
                "context_id": f"ctx_auto_{day_offset}_{pattern['entity_id']}",
                "context_user_id": pattern.get("context_user_id"),  # None for automation
                "context_parent_id": pattern.get(
                    "context_parent_id"
                ),  # Has parent = automation triggered
                "context_domain": pattern.get("context_domain"),
            }
        )

    return states


def generate_system_events(pattern, base_date):
    """Generate system events without user context (should be filtered out)."""
    states = []
    state_values = pattern["state_values"]
    hours_between = pattern["hours_between"]

    for day_offset in range(pattern["days"]):
        day = base_date - timedelta(days=day_offset)

        # Generate events throughout the day
        for hour in range(0, 24, hours_between):
            event_time = day.replace(
                hour=hour, minute=random.randint(0, 5), second=random.randint(0, 59), microsecond=0
            )

            state_value = random.choice(state_values)
            states.append(
                {
                    "entity_id": pattern["entity_id"],
                    "state": state_value,
                    "attributes": json.dumps(
                        {
                            "friendly_name": pattern["entity_id"]
                            .split(".")[1]
                            .replace("_", " ")
                            .title(),
                            "unit_of_measurement": "°C",
                        }
                    ),
                    "last_changed": event_time.isoformat(),
                    "last_updated": event_time.isoformat(),
                    "context_id": f"ctx_sys_{day_offset}_{hour}_{pattern['entity_id']}",
                    "context_user_id": pattern.get("context_user_id"),  # None for system
                    "context_parent_id": pattern.get("context_parent_id"),
                    "context_domain": pattern.get("context_domain"),
                }
            )

    return states


def generate_inconsistent_events(pattern, base_date):
    """Generate random/inconsistent events (below consistency threshold)."""
    states = []
    events_per_day = pattern["events_per_day"]

    for day_offset in range(pattern["days"]):
        day = base_date - timedelta(days=day_offset)

        # Generate events at completely random times
        for event_num in range(events_per_day):
            random_hour = random.randint(0, 23)
            random_minute = random.randint(0, 59)

            event_time = day.replace(
                hour=random_hour, minute=random_minute, second=random.randint(0, 59), microsecond=0
            )

            states.append(
                {
                    "entity_id": pattern["entity_id"],
                    "state": pattern["state"],
                    "attributes": json.dumps(
                        {
                            "friendly_name": pattern["entity_id"]
                            .split(".")[1]
                            .replace("_", " ")
                            .title()
                        }
                    ),
                    "last_changed": event_time.isoformat(),
                    "last_updated": event_time.isoformat(),
                    "context_id": f"ctx_rand_{day_offset}_{event_num}_{pattern['entity_id']}",
                    "context_user_id": pattern.get("context_user_id"),  # Manual but inconsistent
                    "context_parent_id": pattern.get("context_parent_id"),
                    "context_domain": pattern.get("context_domain"),
                }
            )

    return states


def generate_domain_context_events(pattern, base_date):
    """Generate events with specific context_domain (for domain filtering tests)."""
    states = []

    base_hour, base_minute, _ = map(int, pattern["base_time"].split(":"))
    variance = pattern["variance_minutes"]

    for day_offset in range(pattern["days"]):
        day = base_date - timedelta(days=day_offset)

        if pattern["weekdays_only"] and day.weekday() >= 5:
            continue

        minute_offset = random.randint(-variance, variance)
        event_time = day.replace(
            hour=base_hour,
            minute=max(0, min(59, base_minute + minute_offset)),
            second=random.randint(0, 59),
            microsecond=0,
        )

        states.append(
            {
                "entity_id": pattern["entity_id"],
                "state": pattern["state"],
                "attributes": json.dumps(
                    {"friendly_name": pattern["entity_id"].split(".")[1].replace("_", " ").title()}
                ),
                "last_changed": event_time.isoformat(),
                "last_updated": event_time.isoformat(),
                "context_id": f"ctx_domain_{day_offset}_{pattern['entity_id']}",
                "context_user_id": pattern.get("context_user_id"),
                "context_parent_id": pattern.get("context_parent_id"),
                "context_domain": pattern.get("context_domain"),
            }
        )

    return states


def main():
    """Generate the test database."""
    # Ensure directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing database
    if DB_PATH.exists():
        DB_PATH.unlink()

    # Create database
    conn = sqlite3.connect(DB_PATH)
    create_schema(conn)

    cursor = conn.cursor()

    # Generate states for each pattern
    base_date = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
    all_states = []

    # HAPPY PATH: Manual user actions with consistent timing
    print("\nGenerating HAPPY PATH patterns (should be detected):")
    for pattern in PATTERNS:
        states = generate_state_changes(pattern, base_date)
        all_states.extend(states)
        print(
            f"  + {pattern['entity_id']} -> {pattern['state']} around {pattern['base_time']} ({len(states)} events)"
        )

    # UNHAPPY PATH: Events that should be filtered out
    print("\nGenerating UNHAPPY PATH patterns (should be filtered):")

    # Automation-triggered events
    for pattern in AUTOMATION_TRIGGERED_PATTERNS:
        states = generate_automation_triggered_events(pattern, base_date)
        all_states.extend(states)
        print(
            f"  - {pattern['entity_id']} (automation-triggered, has context_parent_id) ({len(states)} events)"
        )

    # Script-triggered events
    for pattern in SCRIPT_TRIGGERED_PATTERNS:
        states = generate_automation_triggered_events(pattern, base_date)  # Same logic
        all_states.extend(states)
        print(
            f"  - {pattern['entity_id']} (script-triggered, has context_parent_id) ({len(states)} events)"
        )

    # System events without user context
    for pattern in SYSTEM_EVENT_PATTERNS:
        states = generate_system_events(pattern, base_date)
        all_states.extend(states)
        print(
            f"  - {pattern['entity_id']} (system event, no context_user_id) ({len(states)} events)"
        )

    # Random/inconsistent events
    for pattern in INCONSISTENT_PATTERNS:
        states = generate_inconsistent_events(pattern, base_date)
        all_states.extend(states)
        print(f"  - {pattern['entity_id']} (inconsistent timing) ({len(states)} events)")

    # Guest user events (for user filtering tests)
    print("\nGenerating USER FILTERING patterns:")
    for pattern in GUEST_USER_PATTERNS:
        states = generate_state_changes(pattern, base_date)
        all_states.extend(states)
        print(
            f"  + {pattern['entity_id']} (guest user: {pattern['context_user_id']}) ({len(states)} events)"
        )

    # Node-RED domain events (for domain filtering tests)
    print("\nGenerating DOMAIN FILTERING patterns:")
    for pattern in NODERED_DOMAIN_PATTERNS:
        states = generate_domain_context_events(pattern, base_date)
        all_states.extend(states)
        print(
            f"  + {pattern['entity_id']} (context_domain: {pattern['context_domain']}) ({len(states)} events)"
        )

    # Insert states
    for state in all_states:
        cursor.execute(
            """
            INSERT INTO states (entity_id, state, attributes, last_changed, last_updated,
                              context_id, context_user_id, context_parent_id, context_domain)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                state["entity_id"],
                state["state"],
                state["attributes"],
                state["last_changed"],
                state["last_updated"],
                state["context_id"],
                state["context_user_id"],
                state["context_parent_id"],
                state.get("context_domain"),
            ),
        )

        # Also insert into states_meta if not exists
        cursor.execute(
            """
            INSERT OR IGNORE INTO states_meta (entity_id) VALUES (?)
        """,
            (state["entity_id"],),
        )

    conn.commit()

    # Print summary
    cursor.execute("SELECT COUNT(*) FROM states")
    count = cursor.fetchone()[0]
    print(f"\n{'='*60}")
    print(f"Created {DB_PATH}")
    print(f"Generated {count} total state records")

    # Show breakdown by entity
    cursor.execute("SELECT entity_id, COUNT(*) FROM states GROUP BY entity_id ORDER BY entity_id")
    print("\nBreakdown by entity:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} events")

    conn.close()


if __name__ == "__main__":
    main()
