# E2E Tests

End-to-end tests that run against a real Home Assistant instance.

## Quick Start

```bash
# Docker mode (default) - uses testcontainers
pytest tests/e2e/ -c tests/e2e/pytest.ini

# Live mode - uses your real HA instance
pytest tests/e2e/ -c tests/e2e/pytest.ini --live
```

> **Important**: Always use `-c tests/e2e/pytest.ini` to disable the socket-blocking plugin.
> See [Socket Blocking Fix](#socket-blocking-fix) for details.

## Test Modes

### Docker Mode (Default)

Uses testcontainers to spin up a Home Assistant Docker container with pre-configured test data.

**Prerequisites:**
```bash
pip install testcontainers requests docker
```

**Running tests:**
```bash
# Run all e2e tests
pytest tests/e2e/ -c tests/e2e/pytest.ini

# Run specific test file
pytest tests/e2e/test_analyzer.py -c tests/e2e/pytest.ini

# Run with verbose logging
pytest tests/e2e/ -c tests/e2e/pytest.ini --log-cli-level=DEBUG
```

### Live Mode

Connects to a running Home Assistant instance using your real data.

**Prerequisites:**
1. A running Home Assistant instance
2. A long-lived access token (create at Profile → Security → Long-Lived Access Tokens)

**Setup:**
```bash
# Copy the example env file
cp .env.e2e.example .env.e2e

# Edit with your credentials
vim .env.e2e
```

**Contents of `.env.e2e`:**
```bash
HA_LIVE_URL=http://homeassistant.local:8123
HA_LIVE_TOKEN=your_long_lived_access_token_here
```

**Running tests:**
```bash
# Run against live HA instance
pytest tests/e2e/ -c tests/e2e/pytest.ini --live

# Run specific live-only tests
pytest tests/e2e/ -c tests/e2e/pytest.ini --live -m live_only

# Run analyzer permutation tests (shows real suggestions)
pytest tests/e2e/test_analyzer_permutations.py -c tests/e2e/pytest.ini --live -v -s
```

**Note:** Tests marked with `@pytest.mark.synthetic_data` are automatically skipped in live mode (they require Docker's test database).

## Socket Blocking Fix

`pytest-homeassistant-custom-component` blocks sockets via `pytest-socket`, which breaks Docker/testcontainers.

**Key discovery**: The plugin registers as `homeassistant` (not `homeassistant-custom-component`):
```
[pytest11]
homeassistant = pytest_homeassistant_custom_component.plugins
```

**Solution**: `tests/e2e/pytest.ini` contains `-p no:homeassistant` to disable the plugin.

**Full documentation**: `docs/solutions/testing/pytest-homeassistant-socket-blocking.md`

## Test Data (Docker Mode)

The Docker tests use pre-configured data in `initial_test_state/`:
- **Auth**: Pre-generated user and long-lived access token (expires 2035)
- **Recorder DB**: Historical state data with detectable patterns:
  - `light.kitchen` on at ~7:00 AM daily
  - `light.kitchen` off at ~8:30 AM daily
  - `light.bedroom` off at ~10:30 PM daily
  - `switch.coffee_maker` on at ~6:45 AM weekdays

## Test Markers

| Marker | Description |
|--------|-------------|
| `@pytest.mark.e2e` | Marks tests as end-to-end (requires Docker or live HA) |
| `@pytest.mark.synthetic_data` | Requires Docker mode synthetic test data |
| `@pytest.mark.live_only` | Requires live mode with real HA instance |

## Fixtures Available

| Fixture | Scope | Description |
|---------|-------|-------------|
| `is_live_mode` | session | Boolean indicating if running in live mode |
| `ha_container` | session | Docker container info (None in live mode) |
| `ha_url` | session | Home Assistant URL |
| `ha_token` | session | Authentication token |
| `ha_api` | function | Configured requests session for API calls |

## Running Specific Tests

```bash
# Run all e2e tests
pytest tests/e2e/ -c tests/e2e/pytest.ini

# Run only Docker mode tests (skip synthetic_data tests)
pytest tests/e2e/ -c tests/e2e/pytest.ini -m "not synthetic_data"

# Run only tests that work in both modes
pytest tests/e2e/ -c tests/e2e/pytest.ini -m "not synthetic_data and not live_only"

# Run a specific test class
pytest tests/e2e/test_analyzer.py::TestAnalyzerPatternDetection -c tests/e2e/pytest.ini
```

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
- False positive filtering (integration vs manual actions)

## Troubleshooting

### Socket Blocked Error
```
pytest_socket.SocketConnectBlockedError: A test tried to use socket.socket.connect()
```
**Fix**: Use `-c tests/e2e/pytest.ini` flag.

### Docker Connection Failed
```
docker.errors.DockerException: Error while fetching server API version
```
**Fix**: Ensure Docker Desktop is running. On macOS, the socket is auto-detected at `~/.docker/run/docker.sock`.

### Live Mode Auth Failed
```
ValueError: Authentication failed for http://homeassistant.local:8123
```
**Fix**: Check your `.env.e2e` file has correct `HA_LIVE_URL` and `HA_LIVE_TOKEN`.

### Module Not Found
```
ModuleNotFoundError: No module named 'custom_components'
```
**Fix**: The `pytest.ini` sets `pythonpath = ../..`. Run from project root or use the `-c` flag.
