# Home Assistant Automation Suggestions

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A custom Home Assistant integration that analyzes your manual actions from the logbook and suggests automations you might want to create. Stop doing the same things manually - let your smart home learn your patterns.

## Features

- **Pattern Detection**: Analyzes logbook history to find repeated manual actions
- **Time-based Suggestions**: Identifies actions performed at consistent times (e.g., turning on lights every evening at 7pm)
- **Configurable Thresholds**: Adjust sensitivity via options flow to match your preferences
- **Rich Sensors**: Exposes suggestion count, top suggestions, and last analysis time
- **On-demand Services**: `analyze_now` to trigger analysis, `dismiss` to hide unwanted suggestions
- **Persistent Notifications**: Alerts you to high-confidence suggestions (80%+)

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
| Min Occurrences | 5 | Minimum times an action must occur to be suggested |
| Consistency Threshold | 70% | How consistent the timing must be |

## Entities Created

| Entity | Type | Description |
|--------|------|-------------|
| `sensor.automation_suggestions_count` | Sensor | Number of pending suggestions |
| `sensor.automation_suggestions_top` | Sensor | Top 5 suggestions in attributes |
| `sensor.automation_suggestions_last_analysis` | Sensor | Timestamp of last analysis |
| `binary_sensor.automation_suggestions_available` | Binary Sensor | On when suggestions exist |

## Services

| Service | Description |
|---------|-------------|
| `automation_suggestions.analyze_now` | Trigger immediate pattern analysis |
| `automation_suggestions.dismiss` | Dismiss a suggestion by ID |

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
