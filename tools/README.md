# Extract Manual Actions

A Python script that queries Home Assistant's logbook to find user-triggered actions and suggests automation candidates.

## Requirements

- Python 3.11+
- `requests` library
- Home Assistant long-lived access token
- Home Assistant instance URL

## Installation

```bash
pip install requests
```

## Configuration

### Environment Variables

Set the following environment variables:

- `HOMEASSISTANT_URL` - Your Home Assistant instance URL (e.g., `http://homeassistant.local:8123`)
- `HA_TOKEN` - Your long-lived access token

Alternatively, you can store your token in a file:

```bash
echo "your-token-here" > ~/.ha_token
chmod 600 ~/.ha_token
```

### Generating a Long-Lived Access Token

1. Open Home Assistant in your browser
2. Click on your profile (bottom left)
3. Navigate to **Security** tab
4. Scroll to **Long-Lived Access Tokens**
5. Click **Create Token**
6. Give it a name (e.g., "Extract Manual Actions Script")
7. Copy the token immediately (it won't be shown again)

## Usage

```bash
# Basic usage (last 7 days)
./extract_manual_actions.py

# Specify time period
./extract_manual_actions.py --days 14

# Override URL via command line
./extract_manual_actions.py --base-url http://192.168.1.100:8123

# JSON output for scripting
./extract_manual_actions.py --json

# Adjust minimum occurrences for automation suggestions
./extract_manual_actions.py --min-occurrences 5
```

## Sample Output

```
Querying Home Assistant at http://homeassistant.local:8123
Time range: 2025-01-15 to 2025-01-22
Domains: light, switch, scene, cover, climate, script
Fetching logbook entries...
Found 2847 total logbook entries
Identified 173 manual actions across 25 entities

=== Manual Actions Summary (Last 7 Days) ===

Entity: scene.living_room_cozy
  Actions: 12 total
  - activated: 12 times (mostly 19:00-21:59)

Entity: light.kitchen_lights
  Actions: 28 total
  - turn_on: 14 times (mostly 06:00-07:59)
  - turn_off: 14 times (mostly 22:00-23:59)

Entity: scene.downstairs_off
  Actions: 8 total
  - activated: 8 times (mostly 22:00-23:59)

=== Automation Candidates ===

1. light.kitchen_lights turn_on
   Pattern: 10 of 14 occurrences around 06:30
   Consistency: 71%
   Suggestion: Create automation for 06:30 trigger

2. light.kitchen_lights turn_off
   Pattern: 11 of 14 occurrences around 22:00
   Consistency: 78%
   Suggestion: Create automation for 22:00 trigger
```

## How It Works

1. **Queries the logbook API** - Fetches entries from Home Assistant's logbook for the specified time period
2. **Filters for user actions** - Identifies actions with a `context_user_id` that were not triggered by automations
3. **Analyzes timing patterns** - Groups actions by entity and time of day to find consistent behaviors
4. **Suggests automations** - Recommends automations for actions that occur 3+ times with consistent timing patterns

## License

MIT
