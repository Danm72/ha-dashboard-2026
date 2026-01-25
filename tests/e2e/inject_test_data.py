#!/usr/bin/env python3
"""
Inject test data for automation suggestions e2e tests.

This script injects historical state changes directly into the Home Assistant
SQLite recorder database with consistent timing patterns and valid context_user_id
values to simulate manual user actions.

Usage:
    python tests/e2e/inject_test_data.py --db-path /path/to/home-assistant_v2.db --user-id USER_ID

The injected data will create patterns that should trigger automation suggestions:
- input_boolean.morning_coffee: turned on around 7:00 AM daily
- input_boolean.evening_lights: turned on around 6:30 PM daily
- input_boolean.bedtime_mode: turned on around 10:00 PM daily
- input_boolean.lunch_break: turned on around 12:00 PM daily
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Test data configuration
TEST_ENTITIES = [
    {
        "entity_id": "input_boolean.morning_coffee",
        "name": "Morning Coffee",
        "icon": "mdi:coffee",
        "target_hour": 7,
        "target_minute": 0,
        "variance_minutes": 15,  # +/- variance from target time
    },
    {
        "entity_id": "input_boolean.evening_lights",
        "name": "Evening Lights",
        "icon": "mdi:lamp",
        "target_hour": 18,
        "target_minute": 30,
        "variance_minutes": 10,
    },
    {
        "entity_id": "input_boolean.bedtime_mode",
        "name": "Bedtime Mode",
        "icon": "mdi:bed",
        "target_hour": 22,
        "target_minute": 0,
        "variance_minutes": 20,
    },
    {
        "entity_id": "input_boolean.lunch_break",
        "name": "Lunch Break",
        "icon": "mdi:food",
        "target_hour": 12,
        "target_minute": 0,
        "variance_minutes": 15,
    },
]


class RecorderDatabase:
    """Direct access to Home Assistant recorder SQLite database."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None

    def connect(self) -> bool:
        """Connect to the database."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            logger.info(f"Connected to database: {self.db_path}")
            return True
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            return False

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def get_schema_info(self) -> dict[str, Any]:
        """Get information about the database schema."""
        if not self.conn:
            return {}

        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        # Check if we have the newer schema with states_meta
        has_states_meta = "states_meta" in tables

        return {
            "tables": tables,
            "has_states_meta": has_states_meta,
        }

    def _ensure_states_meta(self, entity_id: str) -> int | None:
        """Ensure entity exists in states_meta and return metadata_id.

        For newer HA schemas that use states_meta for entity_id deduplication.
        """
        if not self.conn:
            return None

        cursor = self.conn.cursor()

        # Check if states_meta exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='states_meta'")
        if not cursor.fetchone():
            return None  # Old schema, doesn't use states_meta

        # Try to get existing metadata_id
        cursor.execute("SELECT metadata_id FROM states_meta WHERE entity_id = ?", (entity_id,))
        row = cursor.fetchone()
        if row:
            return row[0]

        # Insert new entry
        cursor.execute("INSERT INTO states_meta (entity_id) VALUES (?)", (entity_id,))
        return cursor.lastrowid

    def _ensure_state_attributes(self, attributes: dict[str, Any]) -> int | None:
        """Ensure attributes exist in state_attributes and return attributes_id.

        For newer HA schemas that use state_attributes for attribute deduplication.
        """
        if not self.conn:
            return None

        cursor = self.conn.cursor()

        # Serialize and hash attributes
        attrs_json = json.dumps(attributes, sort_keys=True)
        attrs_hash = hash(attrs_json)

        # Check if attributes already exist
        cursor.execute(
            "SELECT attributes_id FROM state_attributes WHERE hash = ?",
            (attrs_hash,)
        )
        row = cursor.fetchone()
        if row:
            return row[0]

        # Insert new attributes
        cursor.execute(
            "INSERT INTO state_attributes (hash, shared_attrs) VALUES (?, ?)",
            (attrs_hash, attrs_json),
        )
        return cursor.lastrowid

    def inject_state(
        self,
        entity_id: str,
        state: str,
        timestamp: datetime,
        context_user_id: str,
        attributes: dict[str, Any] | None = None,
    ) -> bool:
        """Inject a state change into the database.

        Args:
            entity_id: The entity ID (e.g., "input_boolean.morning_coffee")
            state: The state value (e.g., "on", "off")
            timestamp: When the state change occurred
            context_user_id: User ID to mark this as a manual action
            attributes: Entity attributes (friendly_name, etc.)

        Returns:
            True if successful
        """
        if not self.conn:
            return False

        cursor = self.conn.cursor()

        # Generate unique context_id
        context_id = str(uuid.uuid4())

        # Format timestamp for SQLite (ISO format works)
        ts_str = timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f")

        # Serialize attributes
        attrs_json = json.dumps(attributes) if attributes else "{}"

        try:
            # Check schema version - the states table may have different columns
            cursor.execute("PRAGMA table_info(states)")
            columns = {row[1] for row in cursor.fetchall()}

            if "metadata_id" in columns:
                # Newer schema: uses metadata_id instead of entity_id in states table
                metadata_id = self._ensure_states_meta(entity_id)
                if metadata_id is None:
                    logger.warning(f"Could not get metadata_id for {entity_id}")
                    return False

                # Get or create attributes_id
                attributes_id = self._ensure_state_attributes(attributes or {})

                cursor.execute(
                    """
                    INSERT INTO states
                    (metadata_id, state, attributes_id, last_changed_ts, last_updated_ts,
                     context_id, context_user_id, context_parent_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        metadata_id,
                        state,
                        attributes_id,
                        timestamp.timestamp(),
                        timestamp.timestamp(),
                        context_id,
                        context_user_id,
                        None,
                    ),
                )
            else:
                # Legacy schema: entity_id directly in states table
                # Check what columns actually exist
                if "context_domain" in columns:
                    cursor.execute(
                        """
                        INSERT INTO states
                        (entity_id, state, attributes, last_changed, last_updated,
                         context_id, context_user_id, context_parent_id, context_domain)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            entity_id,
                            state,
                            attrs_json,
                            ts_str,
                            ts_str,
                            context_id,
                            context_user_id,
                            None,
                            None,  # context_domain should NOT be "automation" or "script"
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO states
                        (entity_id, state, attributes, last_changed, last_updated,
                         context_id, context_user_id, context_parent_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            entity_id,
                            state,
                            attrs_json,
                            ts_str,
                            ts_str,
                            context_id,
                            context_user_id,
                            None,
                        ),
                    )

            return True

        except sqlite3.Error as e:
            logger.error(f"Error injecting state for {entity_id}: {e}")
            return False

    def commit(self):
        """Commit changes to database."""
        if self.conn:
            self.conn.commit()

    def get_state_count(self, entity_id: str) -> int:
        """Get number of states for an entity."""
        if not self.conn:
            return 0

        cursor = self.conn.cursor()

        # Check schema type
        cursor.execute("PRAGMA table_info(states)")
        columns = {row[1] for row in cursor.fetchall()}

        if "metadata_id" in columns:
            cursor.execute(
                """
                SELECT COUNT(*) FROM states s
                JOIN states_meta sm ON s.metadata_id = sm.metadata_id
                WHERE sm.entity_id = ?
                """,
                (entity_id,),
            )
        else:
            cursor.execute("SELECT COUNT(*) FROM states WHERE entity_id = ?", (entity_id,))

        row = cursor.fetchone()
        return row[0] if row else 0


def generate_timestamps(
    target_hour: int,
    target_minute: int,
    variance_minutes: int,
    num_days: int = 14,
    skip_probability: float = 0.1,
) -> list[datetime]:
    """Generate timestamps for a pattern over multiple days.

    Args:
        target_hour: Target hour (0-23)
        target_minute: Target minute (0-59)
        variance_minutes: Maximum variance from target time
        num_days: Number of days to generate data for
        skip_probability: Probability of skipping a day (for realism)

    Returns:
        List of datetime objects with the pattern
    """
    timestamps = []
    now = datetime.now()

    for days_ago in range(1, num_days + 1):
        # Skip some days randomly for realism
        if random.random() < skip_probability:
            continue

        # Calculate base time for this day
        base_date = now - timedelta(days=days_ago)
        base_time = base_date.replace(
            hour=target_hour,
            minute=target_minute,
            second=0,
            microsecond=0,
        )

        # Add random variance
        variance = random.randint(-variance_minutes, variance_minutes)
        actual_time = base_time + timedelta(minutes=variance)

        # Add some random seconds for realism
        actual_time = actual_time.replace(second=random.randint(0, 59))

        timestamps.append(actual_time)

    return sorted(timestamps)


def inject_test_data(
    db: RecorderDatabase,
    user_id: str,
    num_days: int = 14,
) -> dict[str, int]:
    """Inject test data for all test entities.

    Args:
        db: Recorder database connection
        user_id: User ID for context_user_id field
        num_days: Number of days of historical data to create

    Returns:
        Dictionary of entity_id -> number of states injected
    """
    results: dict[str, int] = {}

    for entity_config in TEST_ENTITIES:
        entity_id = entity_config["entity_id"]
        name = entity_config["name"]
        icon = entity_config["icon"]

        logger.info(f"Processing {entity_id}...")

        # Generate timestamps for this pattern
        timestamps = generate_timestamps(
            target_hour=entity_config["target_hour"],
            target_minute=entity_config["target_minute"],
            variance_minutes=entity_config["variance_minutes"],
            num_days=num_days,
            skip_probability=0.1,  # Skip ~10% of days
        )

        logger.info(f"  Generated {len(timestamps)} timestamps for pattern")

        # Inject state changes
        attributes = {
            "friendly_name": name,
            "icon": icon,
            "editable": True,
        }

        injected_count = 0
        for ts in timestamps:
            # Inject "on" state (the action we want to detect)
            if db.inject_state(
                entity_id=entity_id,
                state="on",
                timestamp=ts,
                context_user_id=user_id,
                attributes=attributes,
            ):
                injected_count += 1

            # Also inject "off" state a few minutes later (for realism)
            off_time = ts + timedelta(minutes=random.randint(5, 30))
            db.inject_state(
                entity_id=entity_id,
                state="off",
                timestamp=off_time,
                context_user_id=user_id,
                attributes=attributes,
            )

        db.commit()

        # Verify injection
        total_states = db.get_state_count(entity_id)
        results[entity_id] = injected_count
        logger.info(f"  Injected {injected_count} 'on' states, total in DB: {total_states}")

    return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Inject test data for automation suggestions e2e tests"
    )
    parser.add_argument(
        "--db-path",
        "-d",
        required=True,
        help="Path to home-assistant_v2.db",
    )
    parser.add_argument(
        "--user-id",
        "-u",
        required=True,
        help="User ID for context_user_id (from .storage/auth)",
    )
    parser.add_argument(
        "--days",
        "-n",
        type=int,
        default=14,
        help="Number of days of historical data to generate (default: 14)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate database path exists
    db_path = Path(args.db_path)
    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        sys.exit(1)

    logger.info(f"Using database: {db_path}")
    logger.info(f"Using user ID: {args.user_id}")

    if args.dry_run:
        logger.info("DRY RUN - no changes will be made")
        logger.info(f"Would create {len(TEST_ENTITIES)} entity patterns:")
        for entity in TEST_ENTITIES:
            timestamps = generate_timestamps(
                entity["target_hour"],
                entity["target_minute"],
                entity["variance_minutes"],
                args.days,
            )
            logger.info(
                f"  {entity['entity_id']}: ~{len(timestamps)} states around "
                f"{entity['target_hour']:02d}:{entity['target_minute']:02d}"
            )
        sys.exit(0)

    # Connect to database
    db = RecorderDatabase(str(db_path))
    if not db.connect():
        logger.error("Could not connect to database")
        sys.exit(1)

    try:
        # Show schema info
        schema_info = db.get_schema_info()
        logger.info(f"Database schema: {schema_info}")

        # Inject test data
        results = inject_test_data(db, args.user_id, args.days)

        # Summary
        logger.info("=" * 50)
        logger.info("INJECTION SUMMARY")
        logger.info("=" * 50)
        total = 0
        for entity_id, count in results.items():
            logger.info(f"  {entity_id}: {count} states")
            total += count
        logger.info(f"  TOTAL: {total} states injected")
        logger.info("=" * 50)

        if total >= 5 * len(TEST_ENTITIES):
            logger.info("SUCCESS: Injected enough data to trigger suggestions")
        else:
            logger.warning("WARNING: May not have enough data for suggestions")

    finally:
        db.close()


if __name__ == "__main__":
    main()
