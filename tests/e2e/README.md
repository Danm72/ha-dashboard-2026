# E2E Tests

End-to-end tests that run against a real Home Assistant instance.

## Test Modes

### Docker Mode (Default)

Uses testcontainers to spin up a Home Assistant Docker container with pre-configured test data.

**Prerequisites:**
```bash
pip install testcontainers requests docker
```

**Running tests:**
```bash
# Run all e2e tests (requires -p flags to disable socket blocking)
pytest tests/e2e/ -v -m e2e -p no:homeassistant -p no:socket
```

### Live Mode

Connects to a running Home Assistant instance using your real data.

**Prerequisites:**
1. A running Home Assistant instance
2. A long-lived access token (create at Profile -> Security -> Long-Lived Access Tokens)

**Setup:**
```bash
# Copy the example env file
cp .env.e2e.example .env.e2e

# Edit with your credentials
# HA_LIVE_URL=http://homeassistant.local:8123
# HA_LIVE_TOKEN=your_long_lived_access_token_here
```

**Running tests:**
```bash
# Run against live HA instance (uses your real data)
pytest tests/e2e/ -v -m e2e -p no:homeassistant -p no:socket --live
```

**Note:** Some tests that depend on synthetic test data are automatically skipped in live mode. These tests are marked with `@pytest.mark.synthetic_data`.

## Test Data (Docker Mode)

The Docker tests use pre-configured data in `initial_test_state/`:
- **Auth**: Pre-generated user and long-lived access token (expires 2035)
- **Recorder DB**: Historical state data with detectable patterns:
  - `light.kitchen` on at ~7:00 AM daily
  - `light.kitchen` off at ~8:30 AM daily
  - `light.bedroom` off at ~10:30 PM daily
  - `switch.coffee_maker` on at ~6:45 AM weekdays

## Running Specific Tests

```bash
# Run all tests except e2e (uses mocked HA environment)
pytest -m "not e2e"

# Run only Docker mode tests (skip synthetic_data tests)
pytest tests/e2e/ -v -m "e2e and not synthetic_data" -p no:homeassistant -p no:socket

# Run a specific test file
pytest tests/e2e/test_recorder_api.py -v -m e2e -p no:homeassistant -p no:socket

# Run with verbose logging
pytest tests/e2e/ -v -m e2e -p no:homeassistant -p no:socket --log-cli-level=INFO
```

## Fixtures Available

| Fixture | Scope | Description |
|---------|-------|-------------|
| `is_live_mode` | session | Boolean indicating if running in live mode |
| `ha_container` | session | Docker container info (None in live mode) |
| `ha_url` | session | Home Assistant URL |
| `ha_token` | session | Authentication token |
| `ha_api` | function | Configured requests session for API calls |

## Regenerating Test Data (Docker Mode)

If you need to regenerate the test database or auth tokens:

```bash
# Regenerate auth tokens
python tests/e2e/scripts/generate_auth.py

# Regenerate recorder database with patterns
python tests/e2e/scripts/generate_test_db.py
```

## What These Tests Catch

- API compatibility issues (like `session_scope` deprecation)
- Integration loading problems
- Real recorder/logbook behavior
- Pattern detection in actual historical data
- Service registration and sensor creation
