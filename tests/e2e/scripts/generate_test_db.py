#!/usr/bin/env python3
"""
Generate test recorder database with patterns for automation_suggestions analyzer.

This creates a home-assistant_v2.db with historical state data that contains
detectable patterns like:
- Kitchen light turned on around 7:00 AM every day for 14 days
- Bedroom light turned off around 10:30 PM every day for 14 days
- Coffee maker turned on around 6:45 AM on weekdays for 14 days

Run this script to regenerate the test database:
    python tests/e2e/scripts/generate_test_db.py
"""

import sqlite3
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

# Output path
DB_PATH = Path(__file__).parent.parent / "initial_test_state" / "home-assistant_v2.db"

# Test patterns to create
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
            context_parent_id VARCHAR(36)
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
    """Generate state changes for a pattern."""
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
            microsecond=0
        )

        states.append({
            "entity_id": pattern["entity_id"],
            "state": pattern["state"],
            "attributes": json.dumps({"friendly_name": pattern["entity_id"].split(".")[1].replace("_", " ").title()}),
            "last_changed": event_time.isoformat(),
            "last_updated": event_time.isoformat(),
            "context_id": f"ctx_{day_offset}_{pattern['entity_id']}",
            "context_user_id": "e2e_test_user_id_1234567890",  # User-initiated
            "context_parent_id": None,
        })

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

    for pattern in PATTERNS:
        states = generate_state_changes(pattern, base_date)
        all_states.extend(states)

    # Insert states
    for state in all_states:
        cursor.execute("""
            INSERT INTO states (entity_id, state, attributes, last_changed, last_updated,
                              context_id, context_user_id, context_parent_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            state["entity_id"],
            state["state"],
            state["attributes"],
            state["last_changed"],
            state["last_updated"],
            state["context_id"],
            state["context_user_id"],
            state["context_parent_id"],
        ))

        # Also insert into states_meta if not exists
        cursor.execute("""
            INSERT OR IGNORE INTO states_meta (entity_id) VALUES (?)
        """, (state["entity_id"],))

    conn.commit()

    # Print summary
    cursor.execute("SELECT COUNT(*) FROM states")
    count = cursor.fetchone()[0]
    print(f"Created {DB_PATH}")
    print(f"Generated {count} state records")
    print(f"Patterns included:")
    for p in PATTERNS:
        print(f"  - {p['entity_id']} -> {p['state']} around {p['base_time']}")

    conn.close()


if __name__ == "__main__":
    main()
