# Brainstorm: Display Analysis Results in UI

**Date:** 2026-01-23
**Status:** Ready for planning

## What We're Building

A user-friendly way to see automation suggestions without using Developer Tools or parsing sensor attributes.

**Core behavior:**
1. Run analysis automatically on integration install (no manual trigger needed)
2. After each analysis, send ONE persistent notification with ALL recommendations
3. Well-formatted, plain English descriptions
4. Informational only—no action buttons required

## Why This Approach

**User's problem:** Viewing suggestions currently requires navigating to Developer Tools > States, finding the sensor, and reading raw JSON attributes. This is a poor experience.

**Chosen solution:** Persistent notifications because:
- Zero configuration required—appears automatically in HA's notification bell
- Plain English, no metadata to parse
- Already partially implemented (high-confidence suggestions use this)
- Doesn't disrupt existing dashboards or require users to build custom cards

**Rejected alternatives:**
- Custom Lovelace card: Requires JavaScript development and user dashboard configuration
- Dedicated panel: More work, less discoverable for casual users
- Markdown template cards: Requires users to edit their dashboards

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Delivery method | Persistent notification | Zero config, already familiar to users |
| Trigger timing | After each analysis + on install | Eliminates "now what?" for new users |
| Notification count | Single notification | Avoids notification spam |
| Content | All recommendations inline | Users see everything at a glance |
| Actions | Informational only | Keep it simple for V1 |

## Example Notification

```
Automation Suggestions Found

Based on your recent activity, here are some automations you might want to create:

• Turn on Kitchen Light around 7:00 AM
  85% consistent, seen 12 times

• Lock Front Door around 11:00 PM
  78% consistent, seen 8 times

• Turn off Living Room TV around midnight
  72% consistent, seen 6 times

To create these automations, go to Settings > Automations & Scenes.
```

## Implementation Notes

**Changes needed:**

1. **Trigger analysis on install** (`__init__.py` or `coordinator.py`)
   - Call `coordinator.async_refresh()` after setup completes
   - Or schedule initial analysis with short delay

2. **Modify notification logic** (`coordinator.py`)
   - Currently: Only notifies for 80%+ confidence suggestions, one per suggestion
   - New: Single notification after each analysis with ALL suggestions formatted

3. **Format suggestions as readable text**
   - Use `Suggestion.description` field (already has plain English)
   - Or build custom format: "{action} {friendly_name} around {suggested_time}"

## Open Questions

None—ready to proceed to planning.

## Next Steps

Run `/workflows:plan` to create implementation plan.
