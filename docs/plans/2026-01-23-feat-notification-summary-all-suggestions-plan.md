---
title: "feat: Show all suggestions in notification summary"
type: feat
date: 2026-01-23
brainstorm: docs/brainstorms/2026-01-23-ui-notification-summary-brainstorm.md
---

# feat: Show all suggestions in notification summary

## Overview

Modify the notification logic so users see ALL suggestions in a single well-formatted persistent notification after each analysis run—not just high-confidence ones.

**Current behavior:** Only suggestions with ≥80% consistency that haven't been notified before trigger a notification.

**Desired behavior:** Every analysis run sends ONE notification showing ALL suggestions, formatted as plain English recommendations.

## Problem Statement

Users must navigate to Developer Tools > States to see suggestions below 80% confidence. This is a poor experience. The brainstorm concluded that a single, comprehensive notification after each analysis is the simplest way to surface results.

## Proposed Solution

Modify `_async_send_notifications()` in `coordinator.py` to:
1. Include ALL suggestions (remove 80% threshold filter)
2. Always send notification after analysis (remove "already notified" filter)
3. Update message format to match brainstorm example

## Technical Approach

### Files to Modify

| File | Change |
|------|--------|
| `custom_components/automation_suggestions/coordinator.py` | Modify `_async_send_notifications()` |
| `custom_components/automation_suggestions/tests/integration/test_coordinator.py` | Update tests for new behavior |

### Implementation Details

#### coordinator.py changes

**Current** (lines 210-214):
```python
new_high_confidence = [
    s
    for s in suggestions
    if s.consistency_score >= HIGH_CONFIDENCE_THRESHOLD and s.id not in self._notified
]
```

**New:**
```python
# Include all suggestions in notification (no confidence filter)
# Always notify on each analysis run
```

**Message format change** (lines 228-235):

Current:
```
Found {count} {pattern(s)} you might want to automate:

- {suggestion.description}

View all suggestions in the Automation Suggestions sensor.
```

New (per brainstorm):
```
Automation Suggestions Found

Based on your recent activity, here are some automations you might want to create:

• {formatted suggestion 1}
  {consistency}% consistent, seen {count} times

• {formatted suggestion 2}
  {consistency}% consistent, seen {count} times

To create these automations, go to Settings > Automations & Scenes.
```

#### Key decisions

1. **Remove HIGH_CONFIDENCE_THRESHOLD filter** - All suggestions appear
2. **Remove "already notified" check** - Show fresh summary every run
3. **Keep notification_id** - Still replaces previous notification (no spam)
4. **Keep _notified set?** - Can be removed or repurposed (no longer used for filtering)

### Edge Cases

| Scenario | Behavior |
|----------|----------|
| No suggestions found | No notification sent (existing early return) |
| Only dismissed suggestions | No notification (dismissed already filtered in analyzer) |
| First install with no history | No suggestions = no notification |

## Acceptance Criteria

- [x] After each analysis, ONE persistent notification appears
- [x] Notification includes ALL suggestions (not filtered by confidence)
- [x] Notification format matches brainstorm example
- [x] On fresh install, analysis runs and notification appears (if suggestions exist)
- [x] No duplicate notifications (same notification_id replaces previous)

### Testing Requirements

- [x] Unit test: `_async_send_notifications` includes all suggestions
- [x] Unit test: Notification sent even if all suggestions were previously notified
- [x] Unit test: Message format matches expected output
- [x] Unit test: No notification when suggestions list is empty
- [x] Integration test: Full flow from install to notification

## References

- Brainstorm: `docs/brainstorms/2026-01-23-ui-notification-summary-brainstorm.md`
- Current implementation: `custom_components/automation_suggestions/coordinator.py:198-258`
- Constant: `HIGH_CONFIDENCE_THRESHOLD = 0.80` in `const.py:19`
