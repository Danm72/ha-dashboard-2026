# View All Suggestions - Brainstorm

**Date:** 2026-01-24
**Status:** Ready for planning

## User Feedback

From Reddit users:
> "It gave me a suggestion count of 18 but I could only see the top 5? Is there a way to view the other suggestions?"
> "I see I have 44 suggestions but can only view 5. Neat integration so far tho!"
> "Check your HA notifications, you'll see more suggestions but not all of them."

## What We're Building

Two improvements to address the UX gap:

### 1. Custom Lovelace Card

A dedicated card that:
- Displays **all suggestions** (not just top 5)
- Groups by **entity domain** (lights, switches, climate, etc.)
- Supports **pagination or scrolling** for large lists
- Has **dismiss buttons** per suggestion
- Has a **"Scan Now"** button that calls `automation_suggestions.analyze_now`
- Shows suggestion details: entity, action, time, consistency score, occurrence count

### 2. Improved Notification UX

Group suggestions by domain using markdown sections:
```
## 💡 Lights (12 suggestions)
• turn_on Office Light around 08:30
  85% consistent, seen 14 times
...

## 🔌 Switches (5 suggestions)
...
```

This makes a wall of 44 suggestions scannable.

## Why This Approach

- **Custom card inside integration**: Users install one thing via HACS, get everything. No separate card repo to maintain.
- **Collapsible domain sections**: Groups related suggestions, reduces cognitive load.
- **Exposes all suggestions**: The data already exists in `coordinator.data`, just needs UI.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Card location | Inside integration (`www/` folder) | Single installation, simpler for users |
| List display | Grouped by domain with pagination | Handles 40+ suggestions gracefully |
| Notification format | Markdown sections by domain | Scannable without changing existing infra |
| Full list in sensor? | No (use card instead) | Keeps sensor attrs small, card handles display |

## Technical Notes

### Card Implementation

- Location: `custom_components/automation_suggestions/www/automation-suggestions-card.js`
- Register via `__init__.py` using `hass.http.register_static_path`
- User adds via Resources then adds card to dashboard
- Calls existing services: `automation_suggestions.analyze_now`, `automation_suggestions.dismiss`

### Sensor Changes

- **Option A**: Keep top sensor showing only 5 (card fetches from coordinator directly)
- **Option B**: Expose all suggestions in sensor attrs (card reads sensor state)

Option B is simpler for the card - it just reads entity state. Downside: large JSON in state.

### Notification Changes

- Modify `_async_send_notifications()` in coordinator.py
- Group suggestions by domain before formatting
- Use markdown headers: `## 💡 Lights`

## Open Questions

1. **Pagination vs infinite scroll?** - Pagination is simpler to implement, scroll is smoother UX
2. **Max suggestions to show in notification?** - All? Top 20? Should be configurable?
3. **Card styling** - Match HA Material Design? Custom?

## Next Steps

Run `/workflows:plan` to create implementation tasks.
