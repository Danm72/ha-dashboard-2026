---
title: User Filtering for Action Analysis
date: 2026-01-24
issue: "#9"
status: ready-for-planning
---

# User Filtering for Action Analysis

## What We're Building

Add the ability to filter which users' actions are analyzed for automation suggestions. Users can either:
1. **Exclude specific users** (blacklist) - e.g., exclude Node-RED service account, children
2. **Include only specific users** (whitelist) - analyze only selected users

The user chooses the filter mode (exclude/include) and selects which users to apply.

## Use Cases

1. **Service accounts** - Exclude Node-RED, AppDaemon, or other automation tools that have HA user accounts
2. **Children** - Parents may not want suggestions based on kids' irregular usage patterns
3. **Guests** - Temporary users whose patterns shouldn't influence suggestions
4. **Focus on specific users** - Analyze only the primary household members

## Key Decisions

### Filter Mode: Both Exclude and Include
User chooses mode in config flow:
- **Exclude mode** (default): Analyze all users EXCEPT selected ones
- **Include mode**: Analyze ONLY selected users

### User Selection: Multi-select from HA Users
- Use Home Assistant's user selector in config flow
- Shows all HA users by name
- Multi-select allowed

### Implementation Point
Modify `is_manual_action()` in `analyzer.py` to accept excluded/included user IDs and filter based on `context_user_id`.

### Config Storage
New config options:
- `user_filter_mode`: "exclude" | "include" | "none" (default: "none")
- `filtered_users`: list of user IDs

## Edge Cases

1. **Actions without context_user_id** - Physical button presses, Zigbee events, etc. won't have user IDs. These should:
   - In exclude mode: Still be analyzed (no user to exclude)
   - In include mode: Be excluded (no user match)

2. **Non-user integrations** - Node-RED may not always have a user ID. Consider adding option to exclude by `context_domain` as well (future enhancement).

3. **Empty filter list** - If user selects exclude mode but no users, analyze all. If include mode but no users, analyze none.

## Domain Filtering (For Integrations Without HA Users)

### Problem
Some integrations like Node-RED, AppDaemon, and custom addons may:
1. Not have an associated HA user account
2. Have a service account that shows up differently
3. Set `context_domain` but not `context_user_id`

### Solution: Optional Domain Filtering
In addition to user filtering, provide optional domain filtering:

**New config options:**
- `domain_filter_mode`: "exclude" | "include" | "none" (default: "none")
- `filtered_domains`: list of domain strings (e.g., ["nodered", "appdaemon"])

**Common domains to filter:**
- `nodered` - Node-RED addon
- `appdaemon` - AppDaemon automation
- `pyscript` - Python scripts
- `rest_command` - REST API calls
- `shell_command` - Shell commands

### Implementation
Modify `is_manual_action()` to accept domain filter settings similar to user filter:

```python
def is_manual_action(
    entry: dict[str, Any],
    excluded_users: set[str] | None = None,
    included_users: set[str] | None = None,
    excluded_domains: set[str] | None = None,
    included_domains: set[str] | None = None,
) -> bool:
```

### Config Flow Changes
Add a second section/step in config flow:
1. **Step 1**: User filtering (mode + user multi-select)
2. **Step 2**: Domain filtering (mode + text input for domains)

Alternatively, use a single step with collapsible "Advanced" section.

## Updated Open Questions

1. ~~Should we also allow filtering by `context_domain`?~~ **Yes** - See Domain Filtering section above

2. What happens to existing suggestions when filter changes?
   - Suggestions from filtered users/domains should be removed on next analysis

3. Should domain filtering be in the initial release or a follow-up?
   - **Recommended**: Include domain filtering in Phase 1 since it's the same pattern
   - The UI can show domains as a text input (comma-separated) for flexibility

## Success Criteria

### User Filtering
- [ ] Config flow has user filter mode selector (exclude/include/none)
- [ ] Config flow has user multi-select when mode is not "none"
- [ ] `is_manual_action()` respects user filter settings
- [ ] Options flow allows changing user filter settings

### Domain Filtering
- [ ] Config flow has domain filter mode selector (exclude/include/none)
- [ ] Config flow has domain text input when mode is not "none"
- [ ] `is_manual_action()` respects domain filter settings
- [ ] Options flow allows changing domain filter settings

### Testing
- [ ] Unit tests for user filtering logic
- [ ] Unit tests for domain filtering logic
- [ ] Unit tests for combined user + domain filtering
- [ ] Integration tests for config flow with user selection
- [ ] Integration tests for config flow with domain input
