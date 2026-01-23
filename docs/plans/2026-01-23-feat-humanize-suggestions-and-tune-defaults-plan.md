---
title: "feat: Humanize suggestions and tune defaults"
type: feat
date: 2026-01-23
version_bump: 1.0.3 -> 1.1.0
---

# Humanize Suggestions and Tune Defaults

## Overview

Update the automation suggestions integration to:
1. Lower detection thresholds for more permissive suggestion generation
2. Add human-readable descriptions to suggestions
3. Cut a new release (1.1.0)

## Problem Statement

Currently:
- Suggestions are exposed as raw data (`entity_id`, `action`, `suggested_time`, `consistency_score`)
- No human-friendly formatting exists in sensor attributes
- Defaults (`min_occurrences=3`, `threshold=0.50`) produced 18 suggestions in testing
- More permissive settings (`min_occurrences=2`, `threshold=0.3`) produced 39 suggestions

Users need readable descriptions like:
> "Turn on Kitchen Light around 07:00 (85% consistent, seen 12 times)"

## Proposed Solution

### 1. Update Defaults (const.py)

| Constant | Current | New | Rationale |
|----------|---------|-----|-----------|
| `DEFAULT_MIN_OCCURRENCES` | 3 | 2 | Catch patterns earlier |
| `DEFAULT_CONSISTENCY_THRESHOLD` | 0.50 | 0.30 | More permissive detection |

### 2. Add Human-Readable Description to Suggestion

Add a `description` property to the `Suggestion` dataclass that generates text like:

```
"Turn on light.living_room around 07:00 (85% consistent, seen 12 times)"
```

Format pattern:
```
"{Action} {entity_id} around {suggested_time} ({consistency}% consistent, seen {count} times)"
```

Action formatting:
- `turn_on` -> "Turn on"
- `turn_off` -> "Turn off"
- `activated` -> "Activate"
- `executed` -> "Execute"
- `pressed` -> "Press"
- `changed` -> "Change"
- `set_*` -> "Set to *"

### 3. Expose Description in Sensor Attributes

Update `AutomationSuggestionsTopSensor.extra_state_attributes` to include the `description` field in each suggestion dict.

### 4. Version Bump and Release

- Bump `manifest.json` version: `1.0.3` -> `1.1.0`
- Create git tag `v1.1.0`

## Acceptance Criteria

- [x] `DEFAULT_MIN_OCCURRENCES` changed to 2
- [x] `DEFAULT_CONSISTENCY_THRESHOLD` changed to 0.30
- [x] `Suggestion` dataclass has `description` property
- [x] `to_dict()` includes `description` field
- [x] Unit tests cover description generation for all action types
- [x] Existing tests updated for new defaults
- [x] `manifest.json` version is `1.1.0`
- [ ] Git tag `v1.1.0` created

## Technical Approach

### Files to Modify

| File | Changes |
|------|---------|
| `const.py` | Update `DEFAULT_MIN_OCCURRENCES` and `DEFAULT_CONSISTENCY_THRESHOLD` |
| `analyzer.py` | Add `description` property to `Suggestion`, update `to_dict()` |
| `tests/unit/test_analyzer.py` | Add tests for description generation |
| `tests/unit/conftest.py` | Update fixtures if defaults are referenced |
| `manifest.json` | Bump version to `1.1.0` |

### Implementation Details

#### analyzer.py - Add description property

```python
@dataclass
class Suggestion:
    # ... existing fields ...

    @property
    def description(self) -> str:
        """Generate human-readable description of the suggestion."""
        action_display = self._format_action(self.action)
        consistency_pct = int(self.consistency_score * 100)
        return (
            f"{action_display} {self.entity_id} around {self.suggested_time} "
            f"({consistency_pct}% consistent, seen {self.occurrence_count} times)"
        )

    @staticmethod
    def _format_action(action: str) -> str:
        """Convert action code to human-readable verb."""
        action_map = {
            "turn_on": "Turn on",
            "turn_off": "Turn off",
            "activated": "Activate",
            "executed": "Execute",
            "pressed": "Press",
            "changed": "Change",
        }
        if action.startswith("set_"):
            return f"Set to {action[4:]}"
        return action_map.get(action, action.replace("_", " ").capitalize())

    def to_dict(self) -> dict[str, Any]:
        """Convert suggestion to dictionary for serialization."""
        return {
            # ... existing fields ...
            "description": self.description,
        }
```

#### const.py - Update defaults

```python
DEFAULT_MIN_OCCURRENCES = 2  # was 3
DEFAULT_CONSISTENCY_THRESHOLD = 0.30  # was 0.50
```

## Test Plan

### Unit Tests (test_analyzer.py)

```python
def test_suggestion_description_turn_on():
    """Test description for turn_on action."""
    suggestion = Suggestion(
        id="light_living_room_turn_on_07_00",
        entity_id="light.living_room",
        action="turn_on",
        suggested_time="07:00",
        time_window_start="07:00",
        time_window_end="07:29",
        consistency_score=0.85,
        occurrence_count=12,
        last_occurrence="2026-01-22T07:15:00+00:00",
    )
    assert suggestion.description == (
        "Turn on light.living_room around 07:00 (85% consistent, seen 12 times)"
    )

def test_suggestion_description_set_action():
    """Test description for set_* action."""
    suggestion = Suggestion(
        id="climate_hvac_set_cool_18_00",
        entity_id="climate.hvac",
        action="set_cool",
        # ... other fields
    )
    assert "Set to cool" in suggestion.description

def test_to_dict_includes_description():
    """Test that to_dict includes the description field."""
    suggestion = Suggestion(...)
    result = suggestion.to_dict()
    assert "description" in result
    assert result["description"] == suggestion.description
```

### Integration Tests

- Verify sensors expose description in attributes
- Verify new defaults are used when no config options provided

## Release Process

After implementation:

```bash
# Run tests
pytest

# Lint
ruff check . && ruff format --check .

# Commit
git add -A
git commit -m "feat: Add human-readable descriptions to suggestions and tune defaults

- Lower DEFAULT_MIN_OCCURRENCES from 3 to 2
- Lower DEFAULT_CONSISTENCY_THRESHOLD from 0.50 to 0.30
- Add description property to Suggestion dataclass
- Include description in sensor extra_state_attributes

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

# Tag release
git tag -a v1.1.0 -m "Release 1.1.0: Humanized suggestions and tuned defaults"

# Push
git push && git push --tags
```

## References

- Existing notification formatting pattern: `coordinator.py:222-232`
- Suggestion dataclass: `analyzer.py:40-81`
- Sensor attributes: `sensor.py:112-149`
- Permutation test results showing threshold impact
