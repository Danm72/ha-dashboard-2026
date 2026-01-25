---
title: E2E Visual Testing with Docker Database Injection for Home Assistant
category: testing
tags:
  - docker
  - e2e
  - sqlite
  - home-assistant
  - testcontainers
  - database-injection
  - pytest
  - pattern-analysis
module: automation_suggestions
symptom: "Need to test pattern analyzer with realistic data including proper context_user_id values"
root_cause: "Home Assistant APIs don't reliably expose context_user_id through standard history queries like get_significant_states()"
---

# E2E Visual Testing with Docker Database Injection for Home Assistant

## Problem

Testing the automation suggestions integration required realistic user behavior data with proper `context_user_id` values to distinguish manual actions from automation-triggered events. The standard Home Assistant APIs (like `get_significant_states()`) don't reliably return this context information through their public interfaces.

Key challenges:
- The analyzer needs `context_user_id` to identify manual user actions
- `context_parent_id` must be NULL for manual actions (non-NULL indicates automation/script triggered)
- `context_domain` should not be "automation" or "script" for manual actions
- Standard HA history APIs don't expose these context fields consistently

## Solution Overview

Multi-layer E2E testing infrastructure combining:

1. **Docker-based HA container** using testcontainers for isolated testing
2. **Direct SQLite injection** of synthetic test data with proper context fields
3. **Direct SQLite queries** in analyzer as fallback for context data
4. **Browser automation** entry point for visual verification

```
+-------------------+     +------------------+     +-------------------+
|  Test Database    | --> | Docker Container | --> | Pattern Analyzer  |
|  (SQLite inject)  |     | (testcontainers) |     | (direct queries)  |
+-------------------+     +------------------+     +-------------------+
                                   |
                                   v
                          +------------------+
                          | Visual Testing   |
                          | (browser access) |
                          +------------------+
```

## Key Components

### 1. Database Injection Script (tests/e2e/inject_test_data.py)

The `RecorderDatabase` class provides direct SQLite access for injecting test data:

```python
class RecorderDatabase:
    """Direct access to Home Assistant recorder SQLite database."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None

    def get_schema_info(self) -> dict[str, Any]:
        """Get information about the database schema."""
        # Check if we have the newer schema with states_meta
        has_states_meta = "states_meta" in tables
        return {"tables": tables, "has_states_meta": has_states_meta}

    def _ensure_states_meta(self, entity_id: str) -> int | None:
        """Ensure entity exists in states_meta and return metadata_id."""
        # For newer HA schemas that use states_meta for entity_id deduplication
        cursor.execute("SELECT metadata_id FROM states_meta WHERE entity_id = ?", (entity_id,))
        # ... insert if not exists

    def _ensure_state_attributes(self, attributes: dict[str, Any]) -> int | None:
        """Ensure attributes exist in state_attributes and return attributes_id."""
        # For newer HA schemas that use state_attributes for attribute deduplication
        attrs_json = json.dumps(attributes, sort_keys=True)
        attrs_hash = hash(attrs_json)
        # ... check or insert

    def inject_state(
        self,
        entity_id: str,
        state: str,
        timestamp: datetime,
        context_user_id: str,
        attributes: dict[str, Any] | None = None,
    ) -> bool:
        """Inject a state change with proper context_user_id."""
```

Key methods:
- `_ensure_states_meta()` - Handles newer HA schema with metadata_id column
- `_ensure_state_attributes()` - Manages attributes_id for deduplication
- `inject_state()` - Inserts state with proper context_user_id

### 2. Schema Compatibility

Home Assistant's recorder schema has evolved over versions. The injection script handles both:

**Legacy Schema** (entity_id in states table):
```sql
INSERT INTO states
(entity_id, state, attributes, last_changed, last_updated,
 context_id, context_user_id, context_parent_id, context_domain)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
```

**Newer Schema** (metadata_id + states_meta table):
```sql
-- First, ensure entity exists in states_meta
INSERT OR IGNORE INTO states_meta (entity_id) VALUES (?)

-- Then insert state with metadata_id reference
INSERT INTO states
(metadata_id, state, attributes_id, last_changed_ts, last_updated_ts,
 context_id, context_user_id, context_parent_id)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
```

**Schema Detection**:
```python
cursor.execute("PRAGMA table_info(states)")
columns = {row[1] for row in cursor.fetchall()}

if "metadata_id" in columns:
    # Newer schema: uses metadata_id instead of entity_id
    metadata_id = self._ensure_states_meta(entity_id)
    attributes_id = self._ensure_state_attributes(attributes or {})
    # Use metadata_id and attributes_id in INSERT
else:
    # Legacy schema: entity_id directly in states table
    # Use entity_id and attributes JSON in INSERT
```

### 3. Context Preservation Rules

For the analyzer to correctly identify manual user actions:

| Field | Manual Action | Automation Triggered | Script Triggered | System Event |
|-------|--------------|---------------------|------------------|--------------|
| `context_user_id` | Real user ID | NULL | NULL | NULL |
| `context_parent_id` | NULL | Automation context ID | Script context ID | NULL |
| `context_domain` | NULL or empty | "automation" | "script" | Integration domain |

**Injection examples**:

```python
# Manual user action - SHOULD be detected
db.inject_state(
    entity_id="light.kitchen",
    state="on",
    timestamp=datetime.now() - timedelta(hours=1),
    context_user_id="e2e_test_user_id_1234567890",  # Real user ID
    # context_parent_id defaults to None
)

# Automation-triggered - should be FILTERED OUT
cursor.execute(
    """INSERT INTO states (..., context_user_id, context_parent_id)
       VALUES (..., NULL, 'automation_sunset_001')"""
)

# System event - should be FILTERED OUT
cursor.execute(
    """INSERT INTO states (..., context_user_id, context_parent_id)
       VALUES (..., NULL, NULL)"""
)
```

### 4. Test Data Quality

Generate realistic patterns with variance:

```python
def generate_timestamps(
    target_hour: int,
    target_minute: int,
    variance_minutes: int,
    num_days: int = 14,
    skip_probability: float = 0.1,  # Skip ~10% of days for realism
) -> list[datetime]:
    """Generate timestamps for a pattern over multiple days."""
    timestamps = []
    now = datetime.now()

    for days_ago in range(1, num_days + 1):
        # Skip some days randomly for realism
        if random.random() < skip_probability:
            continue

        # Add random variance (10-20 min typical)
        variance = random.randint(-variance_minutes, variance_minutes)
        actual_time = base_time + timedelta(minutes=variance)

        # Add random seconds for realism
        actual_time = actual_time.replace(second=random.randint(0, 59))

        timestamps.append(actual_time)

    return sorted(timestamps)
```

**Pattern configuration example** (from `generate_test_db.py`):

```python
PATTERNS = [
    {
        "entity_id": "light.kitchen",
        "state": "on",
        "base_time": "07:00:00",
        "variance_minutes": 15,  # +/- 15 minutes
        "days": 14,
        "weekdays_only": False,
    },
    {
        "entity_id": "switch.coffee_maker",
        "state": "on",
        "base_time": "06:45:00",
        "variance_minutes": 10,
        "days": 14,
        "weekdays_only": True,  # Only weekdays
    },
]
```

### 5. Docker Container Setup (conftest.py)

The `ha_container` fixture manages the Docker lifecycle:

```python
@pytest.fixture(scope="session")
def ha_container(request):
    """Create Home Assistant container with our custom component installed."""
    if request.config.getoption("--live"):
        yield None  # Live mode: no container
        return

    # Create temporary directory for this test session
    temp_dir = tempfile.mkdtemp(prefix="ha_e2e_test_")
    config_path = Path(temp_dir)

    # Copy initial test state (pre-populated database + auth)
    initial_state_path = Path(__file__).parent / "initial_test_state"
    if initial_state_path.exists():
        shutil.copytree(initial_state_path, config_path, dirs_exist_ok=True)

    # Copy our custom component
    custom_components_src = Path(__file__).parent.parent.parent / "custom_components"
    custom_components_dst = config_path / "custom_components"
    shutil.copytree(custom_components_src, custom_components_dst, dirs_exist_ok=True)

    # Create container
    container = (
        DockerContainer("ghcr.io/home-assistant/home-assistant:stable")
        .with_exposed_ports(8123)
        .with_volume_mapping(str(config_path), "/config", "rw")
        .with_env("TZ", "UTC")
    )

    with container:
        host_port = container.get_exposed_port(8123)
        base_url = f"http://localhost:{host_port}"
        _wait_for_ha_ready(base_url, timeout=120)
        yield {"container": container, "port": host_port, "base_url": base_url}
```

### 6. Visual Testing Entry Point (start_visual_test.py)

For manual browser-based verification:

```bash
python tests/e2e/start_visual_test.py
```

This starts a persistent container and prints:

```
============================================================
HOME ASSISTANT READY FOR VISUAL TESTING
============================================================

URL: http://localhost:32769

To test the Lovelace card:
1. Complete onboarding (if fresh container)
2. Go to Settings > Dashboards > Resources
3. Add resource: /automation_suggestions/automation-suggestions-card.js
4. Create a new dashboard card using type: custom:automation-suggestions-card

============================================================
Press Enter to shut down the container...
============================================================
```

## Prevention Strategies

### Database Corruption Prevention

1. **Always stop HA cleanly before DB modifications**:
   ```bash
   # Stop container before modifying database
   docker stop <container_id>

   # Modify database
   python tests/e2e/inject_test_data.py --db-path /path/to/db --user-id USER_ID

   # Restart container
   docker start <container_id>
   ```

2. **Delete WAL files if corruption occurs**:
   ```bash
   rm /path/to/config/home-assistant_v2.db-wal
   rm /path/to/config/home-assistant_v2.db-shm
   ```

3. **Use transactions for batch operations**:
   ```python
   try:
       # Multiple inject_state() calls
       db.commit()
   except sqlite3.Error:
       db.conn.rollback()
   ```

### Socket Blocking Prevention

Use isolated `pytest.ini` with `-p no:homeassistant` to avoid socket blocking from `pytest-homeassistant-custom-component`:

```ini
# tests/e2e/pytest.ini
[pytest]
addopts =
    -p no:homeassistant
    --strict-markers
    -v
    --tb=short

markers =
    e2e: marks tests as end-to-end (requires Docker)
    synthetic_data: marks tests as requiring synthetic test data
    live_only: marks tests as requiring a live Home Assistant instance

pythonpath = ../..
asyncio_mode = auto
```

See: [pytest-homeassistant-socket-blocking.md](pytest-homeassistant-socket-blocking.md)

## Quick Commands

```bash
# Generate test database with patterns
python tests/e2e/scripts/generate_test_db.py

# Inject additional test data into existing database
python tests/e2e/inject_test_data.py \
    --db-path tests/e2e/initial_test_state/home-assistant_v2.db \
    --user-id e2e_test_user_id_1234567890 \
    --days 14

# Run E2E tests (Docker mode)
pytest tests/e2e/ -c tests/e2e/pytest.ini

# Run E2E tests (Live mode against real HA)
pytest tests/e2e/ -c tests/e2e/pytest.ini --live

# Run only synthetic data tests
pytest tests/e2e/ -c tests/e2e/pytest.ini -m synthetic_data

# Start visual testing container
python tests/e2e/start_visual_test.py

# Run all tests except e2e
pytest --ignore=tests/e2e/
```

## Test Data Patterns

The test database (`tests/e2e/initial_test_state/home-assistant_v2.db`) contains:

### Happy Path (should be detected)

| Entity | Action | Time | Notes |
|--------|--------|------|-------|
| `light.kitchen` | on | ~7:00 AM | Daily with 15min variance |
| `light.kitchen` | off | ~8:30 AM | Daily with 20min variance |
| `light.bedroom` | off | ~10:30 PM | Daily with 15min variance |
| `switch.coffee_maker` | on | ~6:45 AM | Weekdays only, 10min variance |

### Unhappy Path (should be filtered out)

| Entity | Reason | Context |
|--------|--------|---------|
| `light.porch` | Automation-triggered | `context_parent_id` set |
| `switch.morning_routine` | Script-triggered | `context_parent_id` set |
| `sensor.temperature` | System event | No `context_user_id` |
| `light.garage` | Inconsistent timing | Random times, fails consistency threshold |

### Filtering Test Patterns

| Entity | User ID | Domain | Purpose |
|--------|---------|--------|---------|
| `light.guest_room` | `e2e_guest_user_id_9999999999` | - | User filtering test |
| `light.automated_light` | `e2e_test_user_id_1234567890` | `nodered` | Domain filtering test |

## File Structure

```
tests/e2e/
├── __init__.py
├── conftest.py                 # Docker container fixtures, test modes
├── pytest.ini                  # Isolated config (-p no:homeassistant)
├── README.md                   # Quick start guide
├── inject_test_data.py         # RecorderDatabase class for injection
├── start_visual_test.py        # Browser testing entry point
├── test_analyzer.py            # Pattern detection tests
├── test_analyzer_permutations.py
├── test_recorder_api.py        # API compatibility tests
├── test_websocket_api.py
├── initial_test_state/         # Pre-populated HA state
│   ├── home-assistant_v2.db    # Recorder database with patterns
│   ├── .storage/               # Auth tokens, config entries
│   └── configuration.yaml
└── scripts/
    ├── generate_auth.py        # Generate auth tokens
    └── generate_test_db.py     # Generate test database
```

## Troubleshooting

### Database locked error
```
sqlite3.OperationalError: database is locked
```
**Fix**: Stop Home Assistant before modifying the database.

### WAL corruption after crash
```
sqlite3.DatabaseError: file is not a database
```
**Fix**: Delete `.db-wal` and `.db-shm` files, then restart HA.

### Entities not appearing in suggestions
**Possible causes**:
1. Entity not in HA state machine (only in recorder)
2. `context_user_id` is NULL or wrong user
3. `context_parent_id` is set (filtered as automation)
4. Pattern doesn't meet consistency threshold

**Debug**:
```python
cursor.execute("""
    SELECT entity_id, state, context_user_id, context_parent_id
    FROM states
    WHERE entity_id = ?
    ORDER BY last_updated DESC
    LIMIT 10
""", (entity_id,))
```

### Socket blocked error in tests
```
pytest_socket.SocketConnectBlockedError
```
**Fix**: Run with `-c tests/e2e/pytest.ini` flag.

## Related Documentation

- [pytest-homeassistant-socket-blocking.md](pytest-homeassistant-socket-blocking.md) - Socket blocking fix details
- [tests/e2e/README.md](../../../tests/e2e/README.md) - E2E test quick start guide
- [CLAUDE.md](../../../CLAUDE.md) - Project-level documentation
