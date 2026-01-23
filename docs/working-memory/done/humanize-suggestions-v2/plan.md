# Humanize Suggestions v2

## [COMPLETED]

### v1.2.0 Changes
- Added `friendly_name` field to `Suggestion` dataclass
- `description` now uses friendly name when available (e.g., "Turn on Office Curtain" instead of "Turn on cover.office_curtain_2")
- Batched notifications - single notification with bullet list instead of spam
- Fixed false positives from integration-triggered events (UniFi Protect cameras at 03:30 AM)

**False positive fix** (`analyzer.py` lines 167-175):
- `is_manual_action()` now requires `context_user_id` to be a valid value (not "unknown")
- Returns False if no valid user context, preventing state history fallback from marking integration events as manual

### E2E Test Configuration
- Created `tests/e2e/pytest.ini` to isolate e2e tests from `pytest-homeassistant-custom-component`
- Key discovery: plugin registers as `homeassistant` in pytest entry points (not `homeassistant-custom-component`)
- Run e2e tests with: `pytest tests/e2e/ -c tests/e2e/pytest.ini`

## Commits
- `b6fec7a` - feat: Add friendly names, batched notifications, and fix false positives
- `c87e903` - test(e2e): Isolate e2e tests from pytest-homeassistant-custom-component
