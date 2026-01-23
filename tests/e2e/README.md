# E2E Tests

End-to-end tests using real Home Assistant Docker containers.

## Prerequisites

```bash
pip install testcontainers requests docker
```

## Test Data

The tests use pre-configured data in `initial_test_state/`:
- **Auth**: Pre-generated user and long-lived access token (expires 2035)
- **Recorder DB**: Historical state data with detectable patterns:
  - `light.kitchen` on at ~7:00 AM daily
  - `light.kitchen` off at ~8:30 AM daily
  - `light.bedroom` off at ~10:30 PM daily
  - `switch.coffee_maker` on at ~6:45 AM weekdays

## Running Tests

```bash
# Run e2e tests (requires -p flags to disable socket blocking)
pytest tests/e2e/ -v -m e2e -p no:homeassistant -p no:socket

# Run all tests except e2e (uses mocked HA environment)
pytest -m "not e2e"
```

## Regenerating Test Data

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
