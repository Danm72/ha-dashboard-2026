---
title: "feat: Add User and Domain Filtering for Action Analysis"
type: feat
date: 2026-01-24
issue: "#9"
status: completed
---

# feat: Add User and Domain Filtering for Action Analysis

## Overview

Add the ability to filter which users' and domains' actions are analyzed for automation suggestions. Users can choose to exclude specific users/domains (blacklist) or include only specific ones (whitelist).

**Related:** Issue #9, Brainstorm doc `docs/brainstorms/2026-01-24-user-filtering-brainstorm.md`

## Problem Statement / Motivation

Currently, the integration analyzes ALL manual actions in Home Assistant history. This creates problems:

1. **Service accounts** - Node-RED, AppDaemon, or other automation tools with HA user accounts pollute suggestions
2. **Children** - Parents may not want suggestions based on kids' irregular usage patterns
3. **Guests** - Temporary users whose patterns shouldn't influence suggestions
4. **Integration noise** - Some integrations trigger actions without user context

Users need control over whose actions inform their automation suggestions.

## Proposed Solution

### Config Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `user_filter_mode` | enum | `"none"` | `none` / `exclude` / `include` |
| `filtered_users` | list[str] | `[]` | List of user IDs (UUIDs) |
| `domain_filter_mode` | enum | `"none"` | `none` / `exclude` / `include` |
| `filtered_domains` | list[str] | `[]` | List of context_domain strings |

### Filter Logic

```python
def is_manual_action(
    entry: dict[str, Any],
    excluded_users: set[str] | None = None,
    included_users: set[str] | None = None,
    excluded_domains: set[str] | None = None,
    included_domains: set[str] | None = None,
) -> bool:
```

**User filtering (after existing automation checks):**
- `exclude` mode: Return False if `context_user_id` in `excluded_users`
- `include` mode: Return False if `context_user_id` not in `included_users`
- `none` mode: No filtering (current behavior)

**Domain filtering:**
- `exclude` mode: Return False if `context_domain` in `excluded_domains`
- `include` mode: Return False if `context_domain` not in `included_domains`
- `none` mode: No filtering

### Edge Case Behaviors

| Scenario | Exclude Mode | Include Mode |
|----------|--------------|--------------|
| Entry has no `context_user_id` | Keep (no user to exclude) | Skip (no user match) |
| Empty filter list | Analyze all | Analyze none |
| Deleted user in config | Log warning, skip | Log warning, skip |

### Config Flow UI

**User Filtering Section:**
1. Mode selector: "Filter users?" → None / Exclude specific users / Include only specific users
2. User multi-select (visible when mode ≠ none): Shows HA users by name, stores UUIDs

**Domain Filtering Section:**
1. Mode selector: "Filter domains?" → None / Exclude specific domains / Include only specific domains
2. Domain text input (visible when mode ≠ none): Comma-separated list with suggestions

## Technical Considerations

### User Identifier Strategy

Store UUIDs (matches `context_user_id` in logbook), display friendly names in UI.

```python
# Fetch users for selector
users = await hass.auth.async_get_users()
# Filter out system accounts
human_users = [u for u in users if not u.system_generated]
user_options = [{"value": u.id, "label": u.name} for u in human_users]
```

### Performance Impact

Filtering happens in `is_manual_action()` which is already called per-entry. Adding 2-4 set lookups (O(1) each) per entry is negligible.

### Coordinator Config Passing

```python
# coordinator.py - new cached properties
self._user_filter_mode: str = ...
self._filtered_users: set[str] = set(...)
self._domain_filter_mode: str = ...
self._filtered_domains: set[str] = set(...)

# Pass to analyzer
suggestions = await analyze_patterns_async(
    self.hass,
    # existing params...
    excluded_users=self._filtered_users if self._user_filter_mode == "exclude" else None,
    included_users=self._filtered_users if self._user_filter_mode == "include" else None,
    excluded_domains=self._filtered_domains if self._domain_filter_mode == "exclude" else None,
    included_domains=self._filtered_domains if self._domain_filter_mode == "include" else None,
)
```

## Acceptance Criteria

### Functional Requirements

- [x] Config flow shows user filter mode selector
- [x] Config flow shows user multi-select (when mode ≠ none) - Changed to text input for simplicity
- [x] Config flow shows domain filter mode selector
- [x] Config flow shows domain text input (when mode ≠ none)
- [x] Options flow allows changing all filter settings
- [x] `is_manual_action()` correctly filters by user
- [x] `is_manual_action()` correctly filters by domain
- [x] Combined user + domain filtering works correctly
- [x] Edge cases handled per specification

### Testing Requirements

- [x] Unit tests for user exclude mode
- [x] Unit tests for user include mode
- [x] Unit tests for domain exclude mode
- [x] Unit tests for domain include mode
- [x] Unit tests for combined filtering
- [x] Unit tests for edge cases (empty list, no context_user_id)
- [x] Integration tests for config flow with filters
- [x] Integration tests for options flow with filters

## Implementation Tasks

### Phase 1: Core Logic (analyzer.py)

- [x] **const.py**: Add new constants
  - `CONF_USER_FILTER_MODE`, `CONF_FILTERED_USERS`
  - `CONF_DOMAIN_FILTER_MODE`, `CONF_FILTERED_DOMAINS`
  - Default values (`DEFAULT_USER_FILTER_MODE = "none"`, etc.)

- [x] **analyzer.py**: Extend `is_manual_action()` signature
  - Add `excluded_users`, `included_users`, `excluded_domains`, `included_domains` params
  - Implement filtering logic after existing automation checks
  - Update docstring with new parameters

- [x] **test_analyzer.py**: Add unit tests
  - Test user exclude mode (match, no match)
  - Test user include mode (match, no match)
  - Test domain exclude mode (match, no match)
  - Test domain include mode (match, no match)
  - Test combined filtering
  - Test edge cases

### Phase 2: Coordinator Integration (coordinator.py)

- [x] **coordinator.py**: Cache new config values
  - Add `_user_filter_mode`, `_filtered_users` properties
  - Add `_domain_filter_mode`, `_filtered_domains` properties
  - Initialize in `__init__` from config entry

- [x] **coordinator.py**: Pass to analyzer
  - Update `analyze_patterns_async()` call with filter params
  - Update `update_config()` to refresh filter values

- [x] **analyzer.py**: Update `analyze_patterns_async()` signature
  - Add filter parameters
  - Pass to `analyze_logbook_entries()` call

- [x] **analyzer.py**: Update `analyze_logbook_entries()` signature
  - Add filter parameters
  - Pass to `is_manual_action()` calls

### Phase 3: Config Flow (config_flow.py)

- [x] **config_flow.py**: Update `get_config_schema()`
  - Add user filter mode selector
  - Add domain filter mode selector
  - Domain input as text (comma-separated)

- [x] **config_flow.py**: Add user list fetching - Changed to comma-separated text input for simplicity
  - ~~Fetch HA users in `async_step_user()`~~
  - ~~Build `SelectSelector` options from users~~
  - ~~Filter out system accounts~~

- [x] **config_flow.py**: Update data processing
  - Parse comma-separated domain input
  - Store filter config in entry data

- [x] **strings.json**: Add UI strings
  - Labels for filter modes
  - Descriptions for user/domain selection
  - Placeholder text for domain input

- [x] **test_config_flow.py**: Add integration tests
  - Test config flow with filters
  - Test options flow updates filters
  - ~~Test user selector populated correctly~~ - Using text input instead

### Phase 4: Cleanup & Documentation

- [ ] Update CLAUDE.md if needed
- [ ] Test full flow manually
- [ ] Bump version in manifest.json

## Files to Modify

| File | Changes |
|------|---------|
| `const.py` | Add 4 new constants + defaults |
| `analyzer.py` | Extend `is_manual_action()`, `analyze_patterns_async()`, `analyze_logbook_entries()` |
| `coordinator.py` | Cache filter config, pass to analyzer |
| `config_flow.py` | Add filter fields to schema, fetch users |
| `strings.json` | Add UI strings |
| `tests/unit/test_analyzer.py` | Add filter tests |
| `tests/integration/test_config_flow.py` | Add filter config tests |

## Dependencies & Risks

| Risk | Mitigation |
|------|------------|
| `hass.auth.async_get_users()` API changes | Use documented public API, add version check if needed |
| User selector requires HA 2024.1+ | Already require 2024.1.0 in manifest |
| Comma-separated domain input prone to typos | Validate and show warnings for untracked domains |

## Success Metrics

- All existing tests continue to pass
- New filter tests pass with 90%+ coverage on filter logic
- Config flow correctly shows/hides filter fields
- Manual testing confirms filters work as expected

## References & Research

### Internal References

- Brainstorm: `docs/brainstorms/2026-01-24-user-filtering-brainstorm.md`
- Config flow patterns: `config_flow.py:33-57` (schema pattern)
- Coordinator config caching: `coordinator.py:81-93`
- Existing filter logic: `analyzer.py:130-175` (`is_manual_action()`)
- Test patterns: `tests/unit/test_analyzer.py:460-697`

### External References

- HA Selectors: https://www.home-assistant.io/docs/blueprint/selectors/
- HA Config Flow: https://developers.home-assistant.io/docs/config_entries_config_flow_handler/

### Related Work

- Issue #9: Original feature request
- PR #8: Previous config flow refactor (caused regression - lesson learned)
