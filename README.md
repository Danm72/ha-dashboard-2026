# Home Assistant Automation Suggestions

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A custom Home Assistant integration that analyzes your manual actions from the logbook and suggests automations you might want to create. Stop doing the same things manually - let your smart home learn your patterns.

## Features

- **Pattern Detection**: Analyzes logbook history to find repeated manual actions
- **Time-based Suggestions**: Identifies actions performed at consistent times (e.g., turning on lights every evening at 7pm)
- **Configurable Thresholds**: Adjust sensitivity via options flow to match your preferences
- **Rich Sensors**: Exposes suggestion count, top suggestions, and last analysis time
- **On-demand Actions**: `analyze_now` to trigger analysis, `dismiss` to hide unwanted suggestions
- **Persistent Notifications**: Shows all suggestions after each analysis run - no dev tools needed

## Installation via HACS

1. Open HACS in Home Assistant
2. Click the three dots menu → **Custom repositories**
3. Add repository: `https://github.com/Danm72/home-assistant-automation-suggestions`
4. Category: **Integration**
5. Click **Add**
6. Search for "Automation Suggestions" and install
7. Restart Home Assistant
8. Go to Settings → Devices & Services → Add Integration → "Automation Suggestions"

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| Analysis Interval | 7 days | How often to run pattern analysis |
| Lookback Days | 14 | How far back to analyze history |
| Min Occurrences | 2 | Minimum times an action must occur to be suggested |
| Consistency Threshold | 30% | How consistent the timing must be |

## Finding Your Suggestions

### Quick Start

1. **Install the integration**: Go to Settings → Devices & Services → Add Integration → "Automation Suggestions"
2. **Wait for notification**: Analysis runs automatically on install. You'll see a notification with your suggestions.
3. **Create automations**: Use the suggestions to create automations in Settings → Automations & Scenes

**Want to run analysis again?** Call `automation_suggestions.analyze_now` from Developer Tools → Actions.

### Entities Created

| Entity | Type | Description |
|--------|------|-------------|
| `sensor.automation_suggestions_count` | Sensor | Number of pending suggestions |
| `sensor.automation_suggestions_top` | Sensor | Top 5 suggestions with details in attributes |
| `sensor.automation_suggestions_last_analysis` | Sensor | Timestamp of last analysis run |
| `binary_sensor.automation_suggestions_available` | Binary Sensor | On when suggestions exist |

### Understanding Suggestion Output

Each suggestion in `sensor.automation_suggestions_top` attributes includes:

| Field | Example | Description |
|-------|---------|-------------|
| `description` | "Turn on light.kitchen around 07:00 (85% consistent, seen 12 times)" | Human-readable summary |
| `entity_id` | `light.kitchen` | The entity you've been controlling manually |
| `action` | `turn_on` | What action you perform |
| `suggested_time` | `07:00` | When you typically do this |
| `consistency_score` | `0.85` | How reliably you do this at this time (0-1) |
| `occurrence_count` | `12` | Total times this pattern was detected |
| `id` | `light_kitchen_turn_on_07_00` | Unique ID (use with dismiss service) |

## Actions

### `automation_suggestions.analyze_now`

Trigger immediate pattern analysis instead of waiting for the scheduled interval.

**Use cases:**
- After adjusting configuration options
- To refresh suggestions after dismissing some
- To re-run analysis before the scheduled interval

**How to call:** Developer Tools → Actions → `automation_suggestions.analyze_now` → Call Service

### `automation_suggestions.dismiss`

Permanently hide a suggestion you don't want to see again.

**Parameters:**
- `suggestion_id` (required): The unique ID from the suggestion's `id` field

**Example:** To dismiss `light_kitchen_turn_on_07_00`, call the service with that ID.

**Note:** Dismissed suggestions persist across restarts and won't reappear.

## Background

This integration was built using [Claude Code](https://claude.ai/claude-code) with [ha-mcp](https://github.com/homeassistant-ai/ha-mcp) - an MCP server that gives Claude direct access to Home Assistant's API. The full story of how this was created, including the design decisions and lessons learned, is documented in this blog series:

- **[Part 1: The Audit](https://dan-malone.com/blog/home-assistant-ai-implementation)** - Cataloging three years of tech debt
- **[Part 2: The Implementation](https://dan-malone.com/blog/home-assistant-ai-implementation-part-2)** - Building with Claude Code and ha-mcp

---

## Bonus: Dashboard Template

This repository also includes a modern, room-based sections dashboard template for Home Assistant.

![Dashboard Demo](screenshots/demo.gif)

### Dashboard Features

- Room-based navigation with dedicated subviews (Living Room, Kitchen, Bedroom, Office, etc.)
- Quick status badges for presence, solar, heating, and bin collection
- Climate controls with TRV temperature management
- Weather and calendar integration
- Conditional visibility based on entity states

### Dashboard Installation

**Requires**: [navbar-card](https://github.com/nicknomo/lovelace-navbar-card) from HACS

1. Install navbar-card via HACS → Frontend
2. Go to Settings → Dashboards → Add Dashboard
3. Create a new dashboard and switch to YAML mode (Raw configuration editor)
4. Copy contents of `lovelace.dashboard_template.yaml`
5. Replace UPPERCASE placeholders with your entity names:
   - `LIVING_ROOM` → your room name
   - `PERSON_1` → your person entity
   - etc.
6. Save

See the template file for full placeholder documentation.

## License

MIT License - Feel free to use and modify for your own Home Assistant setup.

## Contributing

Contributions welcome! Please open an issue or PR if you have improvements to suggest.
