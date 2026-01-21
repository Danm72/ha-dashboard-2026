# Home Assistant Dashboard 2026

A modern, room-based sections dashboard for Home Assistant featuring quick access navigation, climate controls, and smart home monitoring.

## Demo

https://github.com/user-attachments/assets/demo.mp4

https://github.com/Danm72/ha-dashboard-2026/raw/main/screenshots/demo.mp4

## Overview

This dashboard uses Home Assistant's native **sections view** layout with a consistent room-based navigation pattern. Each room has its own subview with dedicated controls for lights, climate, and sensors.

## Features

- **Room-based navigation**: Dedicated subviews for each room (Living Room, Kitchen, Bedroom, Office, Nursery, Hall, Landing)
- **Quick status badges**: Person presence, solar battery, heating status, hot water temperature, bin collection
- **Climate controls**: TRV temperature controls with visual feedback and comfort temperature settings
- **Motion sensors**: Room occupancy indicators
- **Weather integration**: Daily weather forecast display
- **Calendar integration**: Upcoming events from family calendar
- **Conditional visibility**: Sections show/hide based on entity states (e.g., bin collection reminders only when relevant)

## Views

| View | Path | Description |
|------|------|-------------|
| Home | `/home` | Main overview with weather, calendar, and house status |
| Living Room | `/living-room` | Living room lights and climate |
| Kitchen | `/kitchen` | Kitchen controls |
| Bedroom | `/bedroom` | Bedroom lights and climate |
| Office | `/office` | Office controls |
| Nursery | `/nursery` | Nursery controls |
| Hall | `/hall` | Hallway controls |
| Landing | `/landing` | Landing area controls |

## Required Custom Cards

This dashboard uses the following custom card from HACS:

| Card | Repository | Purpose |
|------|------------|---------|
| [navbar-card](https://github.com/nicknomo/lovelace-navbar-card) | nicknomo/lovelace-navbar-card | Room navigation bar at bottom of each view |

## Installation

### 1. Install Required Cards

Install the navbar-card via HACS:
1. Open HACS in Home Assistant
2. Go to Frontend
3. Search for "navbar-card"
4. Install and restart Home Assistant

### 2. Deploy the Dashboard

**Option A: Copy to storage folder**

1. Copy `lovelace.dashboard_2026` to your Home Assistant `.storage` folder
2. Restart Home Assistant
3. The dashboard will appear in your sidebar

**Option B: Create via UI**

1. Go to Settings > Dashboards > Add Dashboard
2. Create a new dashboard with URL path `dashboard_2026`
3. Switch to YAML mode
4. Copy the contents of `data.config` from this file into your dashboard configuration

### 3. Customize Entity IDs

This dashboard uses specific entity IDs that you'll need to update to match your setup:

- `person.user_1`, `person.user_2` - Your person entities
- `weather.forecast_home` - Your weather entity
- `calendar.family` - Your calendar entity
- `climate.*` - Your climate/TRV entities
- `light.*` - Your light entities
- `sensor.*_temperature` - Your temperature sensors
- `binary_sensor.*_motion*` - Your motion sensors

## Screenshots

See the [demo video](screenshots/demo.mp4) above for a full walkthrough of the dashboard.

## Structure

```
lovelace.dashboard_2026
├── Home view (sections layout)
│   ├── Status badges (persons, solar, heating)
│   ├── Weather forecast
│   ├── Bin collection (conditional)
│   ├── Calendar
│   └── Navigation bar
├── Living Room subview
│   ├── Room status badges
│   ├── Light controls
│   ├── Climate/TRV controls
│   └── Navigation bar
├── Kitchen subview
│   └── ...
└── [Additional room subviews]
```

## Key Patterns

### Navigation Bar

Each view includes a navbar-card at the bottom for quick room switching:

```yaml
type: custom:navbar-card
routes:
  - url: /dashboard_2026/home
    icon: mdi:home
  - url: /dashboard_2026/living-room
    icon: mdi:sofa
  # ... additional rooms
```

### Climate Control Pattern

Each room with heating uses this pattern:
- Comfort temperature input helper (`input_number.*_comfort_temperature`)
- Temperature sensor display
- TRV control tile with climate features

### Conditional Sections

Sections can be hidden/shown based on entity state:

```yaml
visibility:
  - condition: state
    entity: binary_sensor.bin_collection_soon
    state: "on"
```

## Customization

### Adding a New Room

1. Duplicate an existing room view
2. Update the `title` and `path`
3. Update entity IDs to match your room
4. Add the new room to each navbar-card's routes

### Changing Navigation Icons

Update the `icon` property in each navbar-card route to use any MDI icon.

## License

MIT License - Feel free to use and modify for your own Home Assistant setup.

## Contributing

Contributions welcome! Please open an issue or PR if you have improvements to suggest.
