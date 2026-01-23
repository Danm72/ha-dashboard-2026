---
title: "feat: Automation Suggestions Integration V1"
type: feat
date: 2026-01-23
---

# feat: Automation Suggestions Integration V1

## Overview

A Home Assistant custom integration that automatically detects manual action patterns from logbook data and surfaces them as automation candidates via native sensors and notifications.

**V1 Goal:** Prove the pipeline works—detect patterns, expose via sensors, notify users. No YAML generation, no auto-creation.

## Problem Statement

Users repeat the same manual actions (lights, thermostats, scenes) at predictable times but never create automations for them. The existing `extract_manual_actions.py` tool identifies these patterns but requires manual CLI execution—users forget to run it.

## Proposed Solution

A custom integration that:
1. Runs pattern analysis automatically on a schedule (weekly/bi-weekly)
2. Exposes automation candidates as HA sensors
3. Notifies users when strong patterns emerge
4. Allows dismissing suggestions that shouldn't be automated

## Technical Approach

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Home Assistant Core                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐  │
│  │  Config Flow     │    │  Coordinator     │    │  Sensors         │  │
│  │                  │    │                  │    │                  │  │
│  │  - interval      │───▶│  - scheduled     │───▶│  - count         │  │
│  │  - lookback      │    │    analysis      │    │  - top (JSON)    │  │
│  │  - thresholds    │    │  - calls         │    │  - available     │  │
│  │                  │    │    analyzer      │    │  - last_analysis │  │
│  └──────────────────┘    └────────┬─────────┘    └──────────────────┘  │
│                                   │                                      │
│                                   ▼                                      │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐  │
│  │  Services        │    │  Analyzer        │    │  Store           │  │
│  │                  │    │                  │    │                  │  │
│  │  - analyze_now   │───▶│  - query logbook │    │  - dismissed     │  │
│  │  - dismiss       │    │  - detect manual │    │  - last_results  │  │
│  │                  │    │  - find patterns │    │  - config        │  │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### File Structure

```
custom_components/automation_suggestions/
├── __init__.py           # async_setup_entry, async_unload_entry
├── config_flow.py        # ConfigFlow + OptionsFlow
├── coordinator.py        # DataUpdateCoordinator (scheduled analysis)
├── sensor.py             # SensorEntity implementations
├── binary_sensor.py      # BinarySensorEntity (available)
├── services.py           # analyze_now, dismiss handlers
├── analyzer.py           # Pattern detection logic (ported from script)
├── const.py              # DOMAIN, defaults, config keys
├── manifest.json         # Integration metadata
├── strings.json          # Translations
├── services.yaml         # Service definitions
└── translations/
    └── en.json           # English translations
```

### Implementation Phases

#### Phase 1: Scaffold & Core Structure

**Tasks:**
- [ ] Clone HA core repo for scaffold tool access
- [ ] Run `python3 -m script.scaffold integration` with domain `automation_suggestions`
- [ ] Move generated files to `custom_components/automation_suggestions/`
- [ ] Update `manifest.json` with correct metadata
- [ ] Create `const.py` with domain and default values

**manifest.json:**
```json
{
  "domain": "automation_suggestions",
  "name": "Automation Suggestions",
  "codeowners": ["@Danm72"],
  "config_flow": true,
  "dependencies": ["recorder"],
  "documentation": "https://github.com/Danm72/ha-dashboard-2026",
  "integration_type": "service",
  "iot_class": "local_polling",
  "issue_tracker": "https://github.com/Danm72/ha-dashboard-2026/issues",
  "requirements": [],
  "version": "1.0.0"
}
```

**const.py:**
```python
DOMAIN = "automation_suggestions"

# Config keys
CONF_ANALYSIS_INTERVAL = "analysis_interval"
CONF_LOOKBACK_DAYS = "lookback_days"
CONF_MIN_OCCURRENCES = "min_occurrences"
CONF_CONSISTENCY_THRESHOLD = "consistency_threshold"

# Defaults
DEFAULT_ANALYSIS_INTERVAL = 7  # days
DEFAULT_LOOKBACK_DAYS = 14
DEFAULT_MIN_OCCURRENCES = 5
DEFAULT_CONSISTENCY_THRESHOLD = 0.70
DEFAULT_TIME_WINDOW_MINUTES = 30

# Domains to track
TRACKED_DOMAINS = [
    "light", "switch", "cover", "climate", "scene", "script",
    "input_number", "input_boolean", "input_select",
    "input_datetime", "input_button"
]
```

#### Phase 2: Analyzer Module

**Tasks:**
- [ ] Port `extract_manual_actions.py` logic to `analyzer.py`
- [ ] Convert synchronous code to async-compatible (executor-wrapped)
- [ ] Add support for `input_*` domains
- [ ] Use HA's logbook API instead of REST calls
- [ ] Add tests ported from existing test suite

**Key Functions:**
```python
# analyzer.py
async def analyze_patterns(
    hass: HomeAssistant,
    lookback_days: int,
    min_occurrences: int,
    consistency_threshold: float,
    dismissed_suggestions: set[str],
) -> list[Suggestion]
```

**Suggestion Schema:**
```python
@dataclass
class Suggestion:
    id: str                    # "{entity_id}_{action}_{time_window}"
    entity_id: str             # "light.kitchen"
    action: str                # "turn_on"
    suggested_time: str        # "07:00"
    time_window_start: str     # "06:45"
    time_window_end: str       # "07:15"
    consistency_score: float   # 0.85 (0-1 scale)
    occurrence_count: int      # 12
    last_occurrence: str       # ISO timestamp
```

#### Phase 3: Coordinator & Storage

**Tasks:**
- [ ] Create `coordinator.py` with `DataUpdateCoordinator`
- [ ] Set update interval from config (default 7 days)
- [ ] Implement `Store` for dismissed suggestions persistence
- [ ] Run analysis in executor to avoid blocking

**coordinator.py pattern:**
```python
class AutomationSuggestionsCoordinator(DataUpdateCoordinator[list[Suggestion]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(days=entry.options.get(
                CONF_ANALYSIS_INTERVAL, DEFAULT_ANALYSIS_INTERVAL
            )),
        )
        self.config_entry = entry
        self._store = Store(hass, 1, f"{DOMAIN}.dismissed")
        self._dismissed: set[str] = set()

    async def _async_update_data(self) -> list[Suggestion]:
        """Run pattern analysis."""
        return await self.hass.async_add_executor_job(
            analyze_patterns_sync,
            self.hass,
            self._lookback_days,
            self._min_occurrences,
            self._consistency_threshold,
            self._dismissed,
        )
```

#### Phase 4: Sensors

**Tasks:**
- [ ] Create `sensor.py` with count and top suggestions sensors
- [ ] Create `binary_sensor.py` with availability sensor
- [ ] Add `last_analysis` timestamp sensor
- [ ] Implement `CoordinatorEntity` pattern

**Sensors:**

| Entity ID | Type | State | Attributes |
|-----------|------|-------|------------|
| `sensor.automation_suggestions_count` | sensor | `5` (int) | `unit_of_measurement: "suggestions"` |
| `sensor.automation_suggestions_top` | sensor | `5` (count) | `suggestions: [...]` (JSON array) |
| `sensor.automation_suggestions_last_analysis` | sensor | ISO timestamp | `status: "success"/"error"` |
| `binary_sensor.automation_suggestions_available` | binary_sensor | `on`/`off` | - |

#### Phase 5: Services

**Tasks:**
- [ ] Create `services.yaml` with service definitions
- [ ] Implement `analyze_now` service handler
- [ ] Implement `dismiss` service handler
- [ ] Register services in coordinator init

**services.yaml:**
```yaml
analyze_now:
  name: Analyze Now
  description: Trigger immediate pattern analysis.
  fields: {}

dismiss:
  name: Dismiss Suggestion
  description: Permanently hide a suggestion.
  fields:
    suggestion_id:
      name: Suggestion ID
      description: The ID of the suggestion to dismiss.
      required: true
      example: "light.kitchen_turn_on_07:00"
      selector:
        text:
```

#### Phase 6: Config Flow

**Tasks:**
- [ ] Implement `ConfigFlow` for initial setup
- [ ] Implement `OptionsFlow` for reconfiguration
- [ ] Add translations in `strings.json`

**Config Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `analysis_interval` | int | 7 | Days between analyses |
| `lookback_days` | int | 14 | Days of history to analyze |
| `min_occurrences` | int | 5 | Minimum occurrences to suggest |
| `consistency_threshold` | float | 0.70 | Minimum consistency score |

#### Phase 7: Notifications

**Tasks:**
- [ ] Send persistent notification for new high-confidence suggestions
- [ ] Track notified suggestions to avoid spam
- [ ] Format notification with actionable info

**Notification Format:**
```
Title: Automation Suggestion Available
Message: You turn on Kitchen Light around 07:00 daily (85% consistency, 12 occurrences).
         View suggestions in Developer Tools > States > sensor.automation_suggestions_top
```

#### Phase 8: Testing & Documentation

**Goals:**
- Port all existing analyzer tests (113 tests) to the new test structure
- Add comprehensive integration tests for HA components
- Achieve 85%+ overall coverage
- Use pytest-homeassistant-custom-component for HA fixtures

**Tasks:**
- [ ] Set up test directory structure and conftest.py files
- [ ] Port all 113 existing tests from `test_extract_manual_actions.py`
- [ ] Add integration tests for config flow (init, success, already configured)
- [ ] Add integration tests for options flow
- [ ] Add coordinator tests (update success, error handling, dismissed persistence)
- [ ] Add service tests (analyze_now, dismiss)
- [ ] Add sensor tests (count, top, last_analysis, binary_sensor)
- [ ] Create test data factory and fixtures
- [ ] Configure pytest in pyproject.toml
- [ ] Verify coverage meets targets (85%+ overall)
- [ ] Write README.md for HACS

##### Test Directory Structure

```
custom_components/automation_suggestions/
└── tests/
    ├── __init__.py
    ├── conftest.py                    # Root fixtures, test data factory
    ├── test_constants.py              # Shared test tokens, mock configs
    ├── fixtures/
    │   ├── logbook_entries.json       # Sample logbook API responses
    │   ├── patterns.json              # Pre-computed pattern data
    │   └── suggestions.json           # Expected suggestion output
    ├── unit/
    │   ├── __init__.py
    │   ├── conftest.py                # Unit-specific fixtures
    │   └── test_analyzer.py           # Ported from existing 113 tests
    └── integration/
        ├── __init__.py
        ├── conftest.py                # HA fixtures (hass, config_entry)
        ├── test_config_flow.py        # ConfigFlow + OptionsFlow tests
        ├── test_coordinator.py        # DataUpdateCoordinator tests
        ├── test_sensor.py             # Sensor entity tests
        └── test_services.py           # Service handler tests
```

##### Test Categories

**Unit Tests (Fast, Isolated):**

Test pure logic without Home Assistant dependencies. These mock all external calls.

| Module | Test File | Coverage Target |
|--------|-----------|-----------------|
| `analyzer.py` | `tests/unit/test_analyzer.py` | 90% |
| `const.py` | `tests/unit/test_const.py` | 100% |

**Integration Tests (Mocked HA APIs):**

Test HA integration points with mocked Home Assistant internals.

| Component | Test File | Coverage Target |
|-----------|-----------|-----------------|
| Config Flow | `tests/integration/test_config_flow.py` | 85% |
| Coordinator | `tests/integration/test_coordinator.py` | 85% |
| Sensors | `tests/integration/test_sensor.py` | 85% |
| Services | `tests/integration/test_services.py` | 85% |

##### Key Test Cases

**Unit Tests: Analyzer (Port Existing 113 Tests)**

Port all existing test classes from `tools/test_extract_manual_actions.py`:

| Class | Tests | Purpose |
|-------|-------|---------|
| `TestNoneTypeBugFix` | 5 | Null entity_id handling |
| `TestIsManualAction` | 9 | Manual action detection |
| `TestExtractActionFromEntry` | 16 | Domain-specific action extraction |
| `TestParseTimestamp` | 10 | ISO timestamp parsing |
| `TestGetTimeWindow` | 11 | 30-minute time bucketing |
| `TestFormatTimeRange` | 8 | Hour range formatting |
| `TestFindAutomationCandidates` | 8 | Pattern analysis |
| `TestGetLogbookEntries` | 3 | API mocking |
| `TestGetHaToken` | 3 | Token retrieval |
| `TestMalformedLogbookEntries` | 40 | Edge cases/defensive coding |

**Example: Ported Analyzer Test**

```python
# tests/unit/test_analyzer.py
import pytest
from custom_components.automation_suggestions.analyzer import (
    is_manual_action,
    extract_action_from_entry,
    parse_timestamp,
    get_time_window,
    format_time_range,
    find_automation_candidates,
)


class TestIsManualAction:
    """Tests for manual action detection."""

    def test_returns_false_when_no_context_user_id(self):
        """Should return False when context_user_id is missing."""
        entry = {
            "entity_id": "light.living_room",
            "state": "on",
        }
        assert is_manual_action(entry) is False

    def test_returns_true_for_valid_manual_action(self):
        """Should return True for valid manual action with user_id."""
        entry = {
            "entity_id": "light.living_room",
            "state": "on",
            "context_user_id": "user123",
        }
        assert is_manual_action(entry) is True

    def test_returns_false_when_automation_triggered(self):
        """Should return False when context_event_type is automation_triggered."""
        entry = {
            "entity_id": "light.living_room",
            "state": "on",
            "context_user_id": "user123",
            "context_event_type": "automation_triggered",
        }
        assert is_manual_action(entry) is False


class TestMalformedLogbookEntries:
    """Tests for edge cases in HA logbook responses."""

    def test_completely_empty_dict(self):
        """Empty dict should not crash any function."""
        entry = {}
        assert is_manual_action(entry) is False
        assert extract_action_from_entry(entry) == "unknown"

    def test_entity_id_as_integer(self):
        """entity_id as integer instead of string should not crash."""
        entry = {
            "entity_id": 12345,
            "state": "on",
            "context_user_id": "user123",
        }
        result = extract_action_from_entry(entry)
        assert result is not None
```

**Integration Tests: Config Flow**

```python
# tests/integration/test_config_flow.py
import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.automation_suggestions.const import (
    DOMAIN,
    CONF_ANALYSIS_INTERVAL,
    CONF_LOOKBACK_DAYS,
    CONF_MIN_OCCURRENCES,
    CONF_CONSISTENCY_THRESHOLD,
)


class TestConfigFlow:
    """Test the config flow."""

    async def test_flow_init(self, hass):
        """Test flow initialization shows user form."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

    async def test_flow_user_step_success(self, hass):
        """Test successful config flow completion."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_ANALYSIS_INTERVAL: 7,
                CONF_LOOKBACK_DAYS: 14,
                CONF_MIN_OCCURRENCES: 5,
                CONF_CONSISTENCY_THRESHOLD: 0.70,
            },
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Automation Suggestions"
        assert result["data"][CONF_ANALYSIS_INTERVAL] == 7

    async def test_flow_already_configured(self, hass, config_entry):
        """Test we abort if already configured."""
        config_entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "single_instance_allowed"


class TestOptionsFlow:
    """Test the options flow."""

    async def test_options_flow(self, hass, config_entry):
        """Test options flow allows reconfiguration."""
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_ANALYSIS_INTERVAL: 14},
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert config_entry.options[CONF_ANALYSIS_INTERVAL] == 14
```

**Integration Tests: Coordinator**

```python
# tests/integration/test_coordinator.py
import pytest
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.automation_suggestions.coordinator import (
    AutomationSuggestionsCoordinator,
)
from custom_components.automation_suggestions.const import DOMAIN


class TestCoordinator:
    """Test the data update coordinator."""

    async def test_coordinator_update_success(self, hass, config_entry, mock_analyzer):
        """Test successful coordinator update."""
        config_entry.add_to_hass(hass)

        coordinator = AutomationSuggestionsCoordinator(hass, config_entry)
        await coordinator.async_config_entry_first_refresh()

        assert coordinator.data is not None
        assert len(coordinator.data) > 0
        mock_analyzer.assert_called_once()

    async def test_coordinator_update_error_handling(self, hass, config_entry):
        """Test coordinator handles analysis errors gracefully."""
        config_entry.add_to_hass(hass)

        with patch(
            "custom_components.automation_suggestions.coordinator.analyze_patterns",
            side_effect=Exception("Logbook API error"),
        ):
            coordinator = AutomationSuggestionsCoordinator(hass, config_entry)

            with pytest.raises(UpdateFailed):
                await coordinator.async_config_entry_first_refresh()

    async def test_dismissed_suggestions_persist(self, hass, config_entry, mock_store):
        """Test dismissed suggestions are persisted and restored."""
        config_entry.add_to_hass(hass)

        coordinator = AutomationSuggestionsCoordinator(hass, config_entry)
        await coordinator.async_load_dismissed()

        # Dismiss a suggestion
        await coordinator.async_dismiss("light.kitchen_turn_on_07:00")

        assert "light.kitchen_turn_on_07:00" in coordinator.dismissed
        mock_store.async_save.assert_called()
```

**Integration Tests: Services**

```python
# tests/integration/test_services.py
class TestServices:
    """Test service handlers."""

    async def test_analyze_now_service(self, hass, config_entry, mock_analyzer):
        """Test analyze_now service triggers immediate analysis."""
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            DOMAIN,
            "analyze_now",
            {},
            blocking=True,
        )

        # Verify analysis was triggered
        assert mock_analyzer.call_count >= 1

    async def test_dismiss_service(self, hass, config_entry):
        """Test dismiss service hides a suggestion."""
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            DOMAIN,
            "dismiss",
            {"suggestion_id": "light.kitchen_turn_on_07:00"},
            blocking=True,
        )

        coordinator = hass.data[DOMAIN][config_entry.entry_id]
        assert "light.kitchen_turn_on_07:00" in coordinator.dismissed
```

**Integration Tests: Sensors**

```python
# tests/integration/test_sensor.py
import pytest
from homeassistant.const import STATE_UNKNOWN

from custom_components.automation_suggestions.const import DOMAIN


class TestCountSensor:
    """Test the suggestions count sensor."""

    async def test_count_sensor_state(self, hass, config_entry, mock_suggestions):
        """Test count sensor reflects suggestion count."""
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.automation_suggestions_count")
        assert state is not None
        assert state.state == "3"  # From mock_suggestions fixture
        assert state.attributes.get("unit_of_measurement") == "suggestions"


class TestTopSensor:
    """Test the top suggestions sensor."""

    async def test_top_sensor_attributes(self, hass, config_entry, mock_suggestions):
        """Test top sensor has suggestions in attributes."""
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.automation_suggestions_top")
        assert state is not None

        suggestions = state.attributes.get("suggestions", [])
        assert len(suggestions) > 0

        # Verify suggestion structure
        first = suggestions[0]
        assert "entity_id" in first
        assert "action" in first
        assert "consistency" in first


class TestBinarySensor:
    """Test the availability binary sensor."""

    async def test_binary_sensor_available(self, hass, config_entry, mock_suggestions):
        """Test binary sensor is on when suggestions exist."""
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("binary_sensor.automation_suggestions_available")
        assert state is not None
        assert state.state == "on"

    async def test_binary_sensor_unavailable(self, hass, config_entry, empty_suggestions):
        """Test binary sensor is off when no suggestions."""
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("binary_sensor.automation_suggestions_available")
        assert state.state == "off"


class TestLastAnalysisSensor:
    """Test the last analysis timestamp sensor."""

    async def test_last_analysis_timestamp(self, hass, config_entry, mock_suggestions):
        """Test last analysis sensor shows timestamp."""
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.automation_suggestions_last_analysis")
        assert state is not None
        assert state.state != STATE_UNKNOWN
        assert state.attributes.get("status") == "success"
```

##### Fixtures

**Root conftest.py:**

```python
# tests/conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from custom_components.automation_suggestions.const import (
    DOMAIN,
    CONF_ANALYSIS_INTERVAL,
    CONF_LOOKBACK_DAYS,
    CONF_MIN_OCCURRENCES,
    CONF_CONSISTENCY_THRESHOLD,
)


@pytest.fixture
def mock_config_data():
    """Return standard config data for tests."""
    return {
        CONF_ANALYSIS_INTERVAL: 7,
        CONF_LOOKBACK_DAYS: 14,
        CONF_MIN_OCCURRENCES: 5,
        CONF_CONSISTENCY_THRESHOLD: 0.70,
    }


@pytest.fixture
def config_entry(mock_config_data):
    """Create a mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.domain = DOMAIN
    entry.data = mock_config_data
    entry.options = {}
    entry.unique_id = DOMAIN
    entry.title = "Automation Suggestions"
    return entry


@pytest.fixture
def mock_suggestions():
    """Return mock suggestion data."""
    return [
        {
            "id": "light.kitchen_turn_on_07:00",
            "entity_id": "light.kitchen",
            "action": "turn_on",
            "suggested_time": "07:00",
            "consistency_score": 0.85,
            "occurrence_count": 12,
        },
        {
            "id": "light.bedroom_turn_off_22:30",
            "entity_id": "light.bedroom",
            "action": "turn_off",
            "suggested_time": "22:30",
            "consistency_score": 0.92,
            "occurrence_count": 18,
        },
        {
            "id": "switch.coffee_turn_on_06:45",
            "entity_id": "switch.coffee_maker",
            "action": "turn_on",
            "suggested_time": "06:45",
            "consistency_score": 0.78,
            "occurrence_count": 8,
        },
    ]


@pytest.fixture
def empty_suggestions():
    """Return empty suggestion list."""
    return []


@pytest.fixture
def mock_logbook_entries():
    """Return mock logbook API response."""
    return [
        {
            "entity_id": "light.kitchen",
            "state": "on",
            "when": "2026-01-20T07:05:00+00:00",
            "context_user_id": "user123",
        },
        {
            "entity_id": "light.kitchen",
            "state": "on",
            "when": "2026-01-21T07:02:00+00:00",
            "context_user_id": "user123",
        },
        {
            "entity_id": "light.bedroom",
            "state": "off",
            "when": "2026-01-20T22:30:00+00:00",
            "context_user_id": "user123",
        },
    ]
```

**Integration conftest.py:**

```python
# tests/integration/conftest.py
import pytest
from unittest.mock import AsyncMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.fixture
def mock_analyzer(mock_suggestions):
    """Mock the analyze_patterns function."""
    with patch(
        "custom_components.automation_suggestions.coordinator.analyze_patterns",
        new_callable=AsyncMock,
        return_value=mock_suggestions,
    ) as mock:
        yield mock


@pytest.fixture
def mock_store():
    """Mock the Store for persistence."""
    with patch(
        "custom_components.automation_suggestions.coordinator.Store"
    ) as mock_store_class:
        mock_store = AsyncMock()
        mock_store.async_load = AsyncMock(return_value={"dismissed": []})
        mock_store.async_save = AsyncMock()
        mock_store_class.return_value = mock_store
        yield mock_store


@pytest.fixture
def config_entry(mock_config_data):
    """Create a MockConfigEntry for integration tests."""
    return MockConfigEntry(
        domain="automation_suggestions",
        data=mock_config_data,
        options={},
        unique_id="automation_suggestions",
        title="Automation Suggestions",
    )
```

##### Test Data Factory

```python
# tests/test_constants.py
"""Shared test constants and factory methods."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class TestDataFactory:
    """Factory for creating test data."""

    @staticmethod
    def logbook_entry(
        entity_id: str = "light.living_room",
        state: str = "on",
        when: str = "2026-01-20T10:00:00Z",
        context_user_id: str | None = "user123",
        context_event_type: str | None = None,
        context_domain: str | None = None,
    ) -> dict:
        """Create a logbook entry for testing."""
        entry = {
            "entity_id": entity_id,
            "state": state,
            "when": when,
        }
        if context_user_id is not None:
            entry["context_user_id"] = context_user_id
        if context_event_type is not None:
            entry["context_event_type"] = context_event_type
        if context_domain is not None:
            entry["context_domain"] = context_domain
        return entry

    @staticmethod
    def suggestion(
        entity_id: str = "light.kitchen",
        action: str = "turn_on",
        suggested_time: str = "07:00",
        consistency_score: float = 0.85,
        occurrence_count: int = 10,
    ) -> dict:
        """Create a suggestion for testing."""
        return {
            "id": f"{entity_id}_{action}_{suggested_time}",
            "entity_id": entity_id,
            "action": action,
            "suggested_time": suggested_time,
            "consistency_score": consistency_score,
            "occurrence_count": occurrence_count,
        }

    @staticmethod
    def pattern_data(
        total_count: int = 10,
        most_common_window: str = "07:00",
        window_count: int = 8,
        hours: list[int] | None = None,
    ) -> dict:
        """Create pattern analysis data for testing."""
        if hours is None:
            hours = [7] * window_count + [8] * (total_count - window_count)
        return {
            "total_count": total_count,
            "most_common_window": most_common_window,
            "window_count": window_count,
            "hours": hours,
            "time_range": "07:00-08:59" if max(hours) != min(hours) else "07:00",
        }


# Common test tokens
TEST_HA_TOKEN = "test_ha_token_12345"
TEST_USER_ID = "user_abc123"
```

##### pytest Configuration

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["custom_components/automation_suggestions/tests"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
filterwarnings = [
    "ignore::DeprecationWarning",
]
markers = [
    "unit: Unit tests (fast, isolated)",
    "integration: Integration tests (mocked HA)",
]
```

##### Coverage Targets

| Category | Target | Rationale |
|----------|--------|-----------|
| Unit tests (analyzer) | 90% | Core logic, must be reliable |
| Integration tests | 85% | HA-specific code with mocks |
| Overall | 85% | Balance coverage with practicality |

**Coverage Commands:**

```bash
# Run all tests with coverage
pytest --cov=custom_components/automation_suggestions --cov-report=html

# Run unit tests only
pytest -m unit --cov=custom_components/automation_suggestions/analyzer

# Run integration tests only
pytest -m integration
```

##### Test Dependencies

```toml
# pyproject.toml
[project.optional-dependencies]
test = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "pytest-homeassistant-custom-component>=0.13.0",
]
```

##### Mocking Patterns

**Pattern 1: Mock HA Client Init**

```python
@patch.object(HomeAssistantClient, "__init__", lambda self, **kwargs: None)
def test_something(self):
    client = HomeAssistantClient(base_url="http://test")
    # Client created without actual connection
```

**Pattern 2: AsyncMock for Async Methods**

```python
mock_client._request = AsyncMock(return_value={"result": "ok"})
```

**Pattern 3: Assertion Helpers**

```python
def assert_suggestion_valid(suggestion: dict) -> None:
    """Assert a suggestion has all required fields."""
    required = ["id", "entity_id", "action", "consistency_score"]
    for field in required:
        assert field in suggestion, f"Missing field: {field}"
```

### HACS Distribution

**Requirements:**
1. Single integration per repo (or subfolder)
2. Required `manifest.json` keys: domain, documentation, issue_tracker, codeowners, name, version
3. Add to [home-assistant/brands](https://github.com/home-assistant/brands)
4. Create GitHub releases for version selection

**Repository Structure for HACS:**
```
ha-dashboard-2026/
├── custom_components/
│   └── automation_suggestions/
│       ├── __init__.py
│       ├── manifest.json
│       └── ...
├── hacs.json
└── README.md
```

**hacs.json:**
```json
{
  "name": "Automation Suggestions",
  "render_readme": true
}
```

## Acceptance Criteria

### Functional Requirements
- [ ] Integration installs via HACS or manual copy
- [ ] Config flow allows setting analysis interval, lookback, thresholds
- [ ] Scheduled analysis runs at configured interval
- [ ] `analyze_now` service triggers immediate analysis
- [ ] Sensors update with pattern detection results
- [ ] `dismiss` service hides suggestions permanently
- [ ] Persistent notification appears for new suggestions
- [ ] Dismissed suggestions persist across restarts

### Non-Functional Requirements
- [ ] Analysis completes in <30 seconds for 28 days of data
- [ ] No event loop blocking during analysis
- [ ] Graceful handling of logbook API errors
- [ ] Works on HA 2024.1+

### Quality Gates
- [ ] All existing `extract_manual_actions.py` tests pass (ported)
- [ ] Config flow tests pass
- [ ] Integration loads/unloads cleanly
- [ ] No warnings in HA logs during normal operation

## Dependencies & Prerequisites

- Home Assistant 2024.1+ (modern config flow APIs)
- Recorder integration enabled (for logbook access)
- Existing `extract_manual_actions.py` logic (to port)

## Risk Analysis & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Logbook API changes in future HA versions | Medium | High | Pin minimum HA version, test on latest |
| Large logbooks cause slow analysis | Medium | Medium | Run in executor, add timeout, limit lookback |
| False positive patterns annoy users | Medium | Medium | High default thresholds (70%, 5+ occurrences) |
| Users dismiss useful suggestions | Low | Low | Clear notification text, no un-dismiss needed for V1 |

## Open Questions (Resolved)

| Question | Resolution |
|----------|------------|
| Integration vs Add-on? | **Integration** - universal compatibility |
| YAML generation in V1? | **No** - just detection |
| Per-user filtering? | **No** - single-user in V1 |
| Notification type? | **Persistent notification** |
| Time window size? | **30 minutes** (from existing tool) |

## References

### Internal References
- Brainstorm: `docs/brainstorms/2026-01-23-automation-suggestions-brainstorm.md`
- PRD: `docs/PRD-automation-suggestions-integration.md`
- Existing tool: `tools/extract_manual_actions/extract_manual_actions.py`
- Tests: `tools/extract_manual_actions/test_extract_manual_actions.py`
- Coordinator pattern: `infrastructure/docker/ha-config/custom_components/bermuda/coordinator.py`

### External References
- HA Integration Docs: https://developers.home-assistant.io/docs/creating_component_index/
- HA Scaffold Tool: `python3 -m script.scaffold integration`
- HACS Publishing: https://www.hacs.xyz/docs/publish/integration/
- DataUpdateCoordinator: https://developers.home-assistant.io/docs/integration_fetching_data/
- HA Brands: https://github.com/home-assistant/brands
