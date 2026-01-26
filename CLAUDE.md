# Automation Suggestions - Home Assistant Custom Integration

A Home Assistant custom integration that analyzes user behavior patterns from history and suggests automations.

## Build/Test/Lint Commands

```bash
# Run all tests
pytest

# Run unit tests only
pytest custom_components/automation_suggestions/tests/unit/

# Run integration tests only
pytest custom_components/automation_suggestions/tests/integration/

# Run specific test file
pytest custom_components/automation_suggestions/tests/unit/test_analyzer.py

# Run with verbose output
pytest -v

# Lint with ruff
ruff check .

# Format with ruff
ruff format .

# Check formatting without changes
ruff format --check .

# Ensure you're using Python 3.13+ virtual environment
.venv/bin/pytest --ignore=tests/e2e/
```

### Test Configuration
- Requires Python 3.13+ and Home Assistant 2026.1+
- Uses `pytest-homeassistant-custom-component` plugin
- Root `conftest.py` registers the plugin: `pytest_plugins = ["pytest_homeassistant_custom_component"]`
- Tests located in: `custom_components/automation_suggestions/tests/`

### Linting Configuration (pyproject.toml)
- Target: Python 3.13
- Line length: 100
- Rules: F (Pyflakes), E (pycodestyle errors), W (warnings), I (isort), UP (pyupgrade)

## E2E Tests (Docker)

End-to-end tests using real Home Assistant Docker containers via `testcontainers`.

### Prerequisites

```bash
pip install testcontainers requests
```

### Running E2E Tests

```bash
# Run e2e tests (MUST use -c flag for isolated config)
pytest tests/e2e/ -c tests/e2e/pytest.ini

# Run all tests except e2e
pytest --ignore=tests/e2e/

# Run e2e in live mode (against real HA instance)
pytest tests/e2e/ -c tests/e2e/pytest.ini --live
```

### Socket Blocking Fix

`pytest-homeassistant-custom-component` blocks sockets via `pytest-socket`, breaking Docker/testcontainers.

**Key discovery**: The plugin registers as `homeassistant` (not `homeassistant-custom-component`):
```
# From entry_points.txt:
[pytest11]
homeassistant = pytest_homeassistant_custom_component.plugins
```

**Solution**: `tests/e2e/pytest.ini` uses `-p no:homeassistant` to disable the plugin.

See: `docs/solutions/testing/pytest-homeassistant-socket-blocking.md`

### How It Works

The `HomeAssistantTestContainer` class in `tests/e2e/conftest.py`:
1. Creates a temp config directory (copies from `initial_test_state/` if exists)
2. Starts `homeassistant/home-assistant:stable` Docker container
3. Binds port 8123 and mounts config volume
4. Waits for HA to be ready (up to 120s timeout)
5. Provides `ha_url` fixture for tests
6. Cleans up container and temp files on teardown

### Test Files

```
tests/e2e/
├── __init__.py
├── conftest.py           # HomeAssistantTestContainer, fixtures
├── README.md             # Setup instructions
└── test_recorder_api.py  # API compatibility tests
```

### What E2E Tests Catch

- API compatibility issues (e.g., `session_scope` deprecation)
- Real Home Assistant behavior vs mocked behavior
- Integration with actual recorder database

### Setting Up Authenticated Tests

For tests requiring auth:
1. Start a fresh HA container manually
2. Complete onboarding (user: `test` / password: `test`)
3. Generate a long-lived access token
4. Copy `.storage/` directory to `tests/e2e/initial_test_state/`
5. Update `TEST_TOKEN` in `conftest.py`

## Visual E2E Tests (CRITICAL QA)

**Visual E2E testing with Chrome MCP is a CRITICAL part of QA.** Unit and integration tests verify logic, but visual tests verify the actual user experience in a real browser against a real Home Assistant instance.

### Why Visual E2E is Critical

- Catches UI rendering issues that mocked tests miss
- Verifies Lovelace card JavaScript works in real HA environment
- Tests WebSocket subscriptions with real coordinator updates
- Validates CSS styling, tab switching, button interactions
- Screenshots provide evidence that features actually work

### Running Visual E2E Tests

```bash
# 1. Start the Docker container with custom component
python tests/e2e/start_visual_test.py

# 2. Use Chrome MCP tools to run visual tests:
#    - Navigate to the HA URL printed by the script
#    - Complete onboarding if fresh container
#    - Configure the integration
#    - Add the Lovelace card
#    - Take screenshots and verify UI elements
```

### Visual Test Specifications

Visual test procedures are documented in:
- `tests/e2e/visual_test_stale_automations.md` - Stale automation card tests

### Chrome MCP Tools for Visual Testing

Key tools for visual E2E:
- `mcp__claude-in-chrome__tabs_context_mcp` - Get browser tab context
- `mcp__claude-in-chrome__navigate` - Navigate to URLs
- `mcp__claude-in-chrome__computer` (action: screenshot) - Take screenshots
- `mcp__claude-in-chrome__read_page` - Read DOM/accessibility tree
- `mcp__claude-in-chrome__computer` (action: left_click) - Click elements

### QA Checklist

Before merging any Lovelace card changes:
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] E2E API tests pass
- [ ] **Visual E2E tests pass with screenshots** ← CRITICAL

## Architecture

### Key Components

1. **coordinator.py** - `AutomationSuggestionsCoordinator`
   - Extends `DataUpdateCoordinator[list[Suggestion]]`
   - Manages scheduled pattern analysis (default: weekly)
   - Persists dismissed/notified suggestions via `homeassistant.helpers.storage.Store`
   - Sends persistent notifications for high-confidence (80%+) suggestions

2. **analyzer.py** - Pattern Analysis Engine
   - `analyze_patterns_async()` - Main async entry point for HA (queries recorder history)
   - `analyze_logbook_entries()` - Sync function for executor (CPU-bound analysis)
   - Pure sync helper functions for testability: `is_manual_action()`, `extract_action_from_entry()`, `parse_timestamp()`
   - `Suggestion` dataclass for representing automation candidates

3. **sensor.py** - Suggestion Sensors
   - `AutomationSuggestionsCountSensor` - Number of active suggestions
   - `AutomationSuggestionsTopSensor` - Top 5 suggestions in `extra_state_attributes`
   - `AutomationSuggestionsLastAnalysisSensor` - Timestamp of last analysis (device_class: TIMESTAMP)

4. **binary_sensor.py** - `AutomationSuggestionsAvailableBinarySensor`
   - Indicates whether any suggestions are available

5. **services.py** - Service Definitions
   - `analyze_now` - Trigger manual pattern analysis
   - `dismiss` - Dismiss a specific suggestion (requires `suggestion_id`)

6. **config_flow.py** - Setup and Options Flow
   - Single-instance integration (uses DOMAIN as unique_id)
   - Config flow for initial setup
   - Options flow for adjusting parameters post-setup

### Data Flow
1. Coordinator schedules `_async_update_data()` on configured interval
2. Calls `analyze_patterns_async()` which fetches state history via recorder
3. Converts state history to entry dicts, runs analysis in executor
4. Pattern analysis identifies recurring manual actions
5. Results stored as `list[Suggestion]` in `coordinator.data`
6. Sensors read from coordinator data via `CoordinatorEntity`
7. High-confidence suggestions trigger persistent notifications

### Configuration Options (const.py)
| Option | Key | Default | Description |
|--------|-----|---------|-------------|
| Analysis Interval | `analysis_interval` | 7 days | Days between analyses |
| Lookback Days | `lookback_days` | 14 days | Days of history to analyze |
| Min Occurrences | `min_occurrences` | 5 | Minimum pattern occurrences |
| Consistency Threshold | `consistency_threshold` | 0.70 | Minimum consistency score (0-1) |
| Time Window | `DEFAULT_TIME_WINDOW_MINUTES` | 30 min | Grouping window for patterns |
| High Confidence | `HIGH_CONFIDENCE_THRESHOLD` | 0.80 | Threshold for notifications |

### Tracked Domains
```python
TRACKED_DOMAINS = [
    "light", "switch", "cover", "climate", "scene", "script",
    "input_number", "input_boolean", "input_select",
    "input_datetime", "input_button"
]
```

## Key Patterns

- **Runtime Data Pattern**: Uses `entry.runtime_data` to store coordinator instance
- **Sync/Async Separation**: Pure sync functions in analyzer.py for easy unit testing, async wrapper for HA
- **DataUpdateCoordinator**: Standard HA pattern for scheduled data fetching with automatic retry
- **CoordinatorEntity**: All sensors extend this for automatic state updates
- **Persistent Storage**: Uses `homeassistant.helpers.storage.Store` for dismissed/notified persistence
- **Single Instance**: Config flow uses `async_set_unique_id(DOMAIN)` + `_abort_if_unique_id_configured()`

## File Structure

```
custom_components/automation_suggestions/
├── __init__.py          # Integration setup, platform forwarding
├── analyzer.py          # Pattern analysis logic + Suggestion dataclass
├── binary_sensor.py     # Availability binary sensor
├── config_flow.py       # Config and options flows
├── const.py             # Constants, defaults, tracked domains
├── coordinator.py       # DataUpdateCoordinator subclass
├── sensor.py            # Count, Top, LastAnalysis sensors
├── services.py          # Service handlers (analyze_now, dismiss)
├── strings.json         # UI strings
├── translations/en.json # English translations
├── manifest.json        # Integration manifest
└── tests/
    ├── __init__.py
    ├── conftest.py          # Shared fixtures
    ├── test_constants.py
    ├── unit/
    │   ├── __init__.py
    │   ├── conftest.py
    │   └── test_analyzer.py
    └── integration/
        ├── __init__.py
        ├── conftest.py
        ├── test_config_flow.py
        ├── test_coordinator.py
        ├── test_sensor.py
        └── test_services.py
```

## Dependencies

From `manifest.json`:
- `logbook` - For user action history concepts
- `recorder` - Required for state history queries (`get_significant_states`)

## HACS Installation

Configured for HACS in `hacs.json`:
- Minimum HA version: 2026.1.0
- Content not in root (`content_in_root: false`)

## Tools Directory

Standalone scripts in `tools/`:
- `extract_manual_actions.py` - CLI tool to extract manual actions from HA logbook API
- `test_extract_manual_actions.py` - Tests for the extraction script
