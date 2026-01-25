---
title: "feat: Add Lovelace Card to View All Suggestions"
type: feat
date: 2026-01-24
deepened: 2026-01-24
---

# feat: Add Lovelace Card to View All Suggestions

## Enhancement Summary

**Deepened on:** 2026-01-24
**Research agents used:** architecture-strategist, kieran-python-reviewer, julik-frontend-races-reviewer, code-simplicity-reviewer, performance-oracle, best-practices-researcher, framework-docs-researcher

### Critical Architectural Change

**BLOCKING ISSUE DISCOVERED:** The original plan to expose all suggestions in sensor `extra_state_attributes` (~50KB for 100 suggestions) **violates Home Assistant's 16KB hard limit** for state attributes. Attributes exceeding this limit are silently truncated by the recorder.

**Revised approach:** Implement a **WebSocket API** for paginated data access. The card fetches suggestions via WebSocket instead of reading sensor state.

### Key Improvements from Research

1. **WebSocket API** instead of bloated sensor attributes (architecture-strategist)
2. **Race condition guards** for Scan Now button (julik-frontend-races-reviewer)
3. **State change detection** to prevent excessive re-renders (performance-oracle)
4. **Proper lifecycle methods** with cleanup (julik-frontend-races-reviewer)
5. **Python code fixes**: top-level imports, public method for action formatting (kieran-python-reviewer)

### Alternative Considered (Simpler)

The simplicity-reviewer noted: A **Markdown card with Jinja template** reading sensor attributes (keeping top 5 limit) solves 80% of the problem with 1 line of template code. Consider this for a quick V0.5 release before the full card.

---

## Overview

Users report seeing "18 suggestions" or "44 suggestions" in the count sensor but can only view the top 5. This plan adds a custom Lovelace card to display ALL suggestions with domain grouping, dismiss buttons, and a scan trigger—plus improved notification formatting.

**User feedback from Reddit:**
> "It gave me a suggestion count of 18 but I could only see the top 5?"
> "I see I have 44 suggestions but can only view 5."

## Problem Statement

The current integration exposes suggestion data via:
- **Count sensor**: Shows total count (e.g., 44)
- **Top sensor**: Only shows top 5 in `extra_state_attributes`
- **Notifications**: Shows all but as a flat wall of text

Users need a way to browse all suggestions, especially when counts are high.

## Proposed Solution

### 1. Custom Lovelace Card

A JavaScript card bundled with the integration that:
- Displays **all suggestions** grouped by entity domain
- Supports **collapsible domain sections** with counts
- Has **dismiss buttons** per suggestion (calls `automation_suggestions.dismiss`)
- Has **"Scan Now" button** (calls `automation_suggestions.analyze_now`)
- Shows full suggestion details: entity name, action, time, consistency %, occurrence count

### 2. WebSocket API for Suggestions Data

~~Modify `AutomationSuggestionsTopSensor` to expose ALL suggestions in `extra_state_attributes`.~~

**REVISED:** Implement a WebSocket API endpoint for paginated suggestion retrieval. This avoids the 16KB attribute limit and enables efficient data transfer.

### 3. Improved Notification Formatting

Group suggestions by domain with markdown headers and emoji icons:

```
## 💡 Lights (12 suggestions)
• Turn on Office Light around 08:30
  85% consistent, seen 14 times
• Turn off Kitchen Light around 22:00
  92% consistent, seen 18 times

## 🔌 Switches (5 suggestions)
• Turn on Coffee Maker around 07:00
  78% consistent, seen 10 times
```

## Technical Approach

### File Changes

| File | Change |
|------|--------|
| `websocket_api.py` | **NEW** - WebSocket handlers for suggestion listing |
| `coordinator.py` | Group notifications by domain with emoji headers |
| `__init__.py` | Register WebSocket commands and static path for card JS |
| `www/automation-suggestions-card.js` | **NEW** - Lovelace card implementation |
| `const.py` | Add domain-to-emoji mapping |
| `analyzer.py` | Make `_format_action()` public → `format_action()` |

### Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Lovelace Dashboard                     │
│  ┌────────────────────────────────────────────────────┐  │
│  │        automation-suggestions-card                  │  │
│  │  ┌──────────────────────────────────────────────┐  │  │
│  │  │  💡 Lights (12)              [▼ collapse]    │  │  │
│  │  │  ├─ Turn on Office Light @ 08:30  [Dismiss]  │  │  │
│  │  │  │   85% consistent, seen 14 times           │  │  │
│  │  │  └─ Turn off Kitchen @ 22:00      [Dismiss]  │  │  │
│  │  ├──────────────────────────────────────────────┤  │  │
│  │  │  🔌 Switches (5)             [▼ collapse]    │  │  │
│  │  │  └─ ...                                      │  │  │
│  │  ├──────────────────────────────────────────────┤  │  │
│  │  │  [ 🔄 Scan Now ]   Page 1 of 3 [< >]        │  │  │
│  │  └──────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
          │                              │
          │ WebSocket                    │ calls service
          ▼                              ▼
┌─────────────────────────┐    ┌─────────────────────────────┐
│ WebSocket API           │    │ automation_suggestions.     │
│                         │    │ dismiss / analyze_now       │
│ automation_suggestions/ │    │                             │
│   list                  │    │                             │
│   subscribe             │    │                             │
└─────────────────────────┘    └─────────────────────────────┘
          │
          ▼
┌─────────────────────────┐
│ Coordinator             │
│ coordinator.data        │
│ (full list[Suggestion]) │
└─────────────────────────┘
```

## Acceptance Criteria

### Card Functionality
- [x] Card fetches suggestions via WebSocket API (not sensor attributes)
- [x] Suggestions grouped by entity domain with collapsible sections
- [x] Domain sections show count in header (e.g., "Lights (12)")
- [x] Each suggestion shows: friendly name, action, time, consistency %, occurrences
- [x] Dismiss button per suggestion calls `automation_suggestions.dismiss` service
- [x] "Scan Now" button calls `automation_suggestions.analyze_now` service
- [x] Scan Now button shows spinner and is disabled during scan (with re-entry guard)
- [x] Card updates automatically via WebSocket subscription

### Card UX
- [x] Empty state when 0 suggestions ("No suggestions yet. Click Scan Now to analyze patterns.")
- [x] Loading state while fetching initial data
- [x] Error state with retry button on service call failures
- [x] Domain sections sorted by suggestion count (highest first)
- [x] All domain sections expanded by default
- [x] Pagination when >20 suggestions total (configurable via card YAML)
- [x] Uses HA CSS custom properties for theming (dark mode compatible)

### Card Technical Quality
- [x] Proper `connectedCallback`/`disconnectedCallback` lifecycle methods
- [x] WebSocket subscription cleanup on disconnect
- [x] State change detection to prevent excessive re-renders
- [x] Event delegation for button handlers (not per-element listeners)
- [x] Memoized domain grouping computation

### Card Installation
- [x] Card JS file at `www/automation-suggestions-card.js`
- [x] Static path registered via `__init__.py`
- [x] WebSocket API registered via `__init__.py`
- [x] User can add card via Lovelace Resources + YAML config
- [ ] Documentation for adding the card

### WebSocket API
- [x] `automation_suggestions/list` - Returns paginated suggestions
- [x] `automation_suggestions/subscribe` - Real-time updates when data changes
- [x] Server-side pagination (page, page_size parameters)

### Notification Improvements
- [x] Suggestions grouped by domain with emoji headers
- [x] Domain emoji mapping: light→💡, switch→🔌, cover→🚪, climate→🌡️, scene→🎬, script→📜, input_*→⚙️
- [x] Actions use `Suggestion.format_action()` (public method) for proper display

### Testing
- [x] Unit tests for domain grouping logic
- [x] Unit tests for emoji mapping
- [x] Unit tests for WebSocket handlers
- [ ] Integration test for WebSocket pagination
- [ ] Manual test: card with 0, 5, 50 suggestions
- [ ] Manual test: dismiss flow
- [ ] Manual test: scan now flow (including double-click)

## Implementation Details

### Phase 1: WebSocket API

**File: `websocket_api.py`** (NEW)

```python
"""WebSocket API for Automation Suggestions."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import AutomationSuggestionsCoordinator

_LOGGER = logging.getLogger(__name__)


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register WebSocket API handlers."""
    websocket_api.async_register_command(hass, websocket_list_suggestions)
    websocket_api.async_register_command(hass, websocket_subscribe_suggestions)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "automation_suggestions/list",
        vol.Optional("page", default=1): vol.Coerce(int),
        vol.Optional("page_size", default=20): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=100)
        ),
    }
)
@callback
def websocket_list_suggestions(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Handle list suggestions WebSocket command."""
    coordinator = _get_coordinator(hass)
    if coordinator is None or coordinator.data is None:
        connection.send_result(msg["id"], {"suggestions": [], "total": 0, "page": 1, "pages": 0})
        return

    suggestions = coordinator.data
    total = len(suggestions)
    page = msg["page"]
    page_size = msg["page_size"]
    pages = (total + page_size - 1) // page_size

    start = (page - 1) * page_size
    end = start + page_size
    page_suggestions = [s.to_dict() for s in suggestions[start:end]]

    connection.send_result(
        msg["id"],
        {
            "suggestions": page_suggestions,
            "total": total,
            "page": page,
            "pages": pages,
            "page_size": page_size,
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "automation_suggestions/subscribe",
    }
)
@callback
def websocket_subscribe_suggestions(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Subscribe to suggestion updates."""
    coordinator = _get_coordinator(hass)
    if coordinator is None:
        connection.send_error(msg["id"], "not_found", "Coordinator not found")
        return

    @callback
    def async_on_update() -> None:
        """Send update when coordinator data changes."""
        if coordinator.data is None:
            return
        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                {
                    "suggestions": [s.to_dict() for s in coordinator.data],
                    "total": len(coordinator.data),
                },
            )
        )

    # Subscribe to coordinator updates
    unsub = coordinator.async_add_listener(async_on_update)
    connection.subscriptions[msg["id"]] = unsub

    # Send initial data
    connection.send_result(msg["id"])
    async_on_update()


def _get_coordinator(hass: HomeAssistant) -> AutomationSuggestionsCoordinator | None:
    """Get coordinator from hass data."""
    entries = hass.config_entries.async_entries(DOMAIN)
    for entry in entries:
        if hasattr(entry, "runtime_data") and entry.runtime_data is not None:
            return entry.runtime_data
    return None
```

### Phase 2: Notification Improvements

**File: `const.py`** - Add domain emoji mapping:

```python
DOMAIN_EMOJI_MAP: dict[str, str] = {
    "light": "💡",
    "switch": "🔌",
    "cover": "🚪",
    "climate": "🌡️",
    "scene": "🎬",
    "script": "📜",
    "input_number": "⚙️",
    "input_boolean": "⚙️",
    "input_select": "⚙️",
    "input_datetime": "⚙️",
    "input_button": "⚙️",
}

DEFAULT_EMOJI = "📋"
```

**File: `analyzer.py`** - Make `_format_action()` public:

```python
# Change from:
def _format_action(self) -> str:
# To:
def format_action(self) -> str:
    """Format the action for display (e.g., 'Turn on' instead of 'turn_on')."""
    return self.action.replace("_", " ").title()
```

**File: `coordinator.py`** - Update `_async_send_notifications()`:

```python
from collections import defaultdict  # Move to top of file

from .const import DEFAULT_EMOJI, DOMAIN_EMOJI_MAP


async def _async_send_notifications(self, suggestions: list[Suggestion]) -> None:
    """Send a persistent notification with all suggestions grouped by domain."""
    if not suggestions:
        return

    _LOGGER.debug("Sending notification for %d suggestions", len(suggestions))

    # Group suggestions by domain
    by_domain: dict[str, list[Suggestion]] = defaultdict(list)
    for s in suggestions:
        # Defensive check for malformed entity_id
        if "." not in s.entity_id:
            _LOGGER.warning("Malformed entity_id: %s", s.entity_id)
            continue
        domain = s.entity_id.split(".")[0]
        by_domain[domain].append(s)

    # Build message with domain sections (sorted by count descending)
    sections = []
    for domain in sorted(by_domain.keys(), key=lambda d: -len(by_domain[d])):
        emoji = DOMAIN_EMOJI_MAP.get(domain, DEFAULT_EMOJI)
        count = len(by_domain[domain])
        header = f"## {emoji} {domain.replace('_', ' ').title()} ({count})"

        bullets = []
        for s in by_domain[domain]:
            name = s.friendly_name or s.entity_id
            action = s.format_action()  # Public method
            pct = int(s.consistency_score * 100)
            bullets.append(
                f"• {action} {name} around {s.suggested_time}\n"
                f"  {pct}% consistent, seen {s.occurrence_count} times"
            )

        sections.append(header + "\n" + "\n".join(bullets))

    message = "Based on your recent activity:\n\n" + "\n\n".join(sections)

    try:
        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "Automation Suggestions Found",
                "message": message,
                "notification_id": "automation_suggestions_batch",
            },
        )
        _LOGGER.debug("Sent notification for %d suggestions", len(suggestions))
    except Exception as err:
        _LOGGER.warning("Failed to send notification: %s", err)
```

### Phase 3: Card Registration

**File: `__init__.py`** - Register WebSocket API and static path:

```python
from homeassistant.components.http import StaticPathConfig

from .websocket_api import async_register_websocket_api


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # ... existing setup ...

    # Register WebSocket API
    async_register_websocket_api(hass)

    # Register frontend static path for Lovelace card (async method)
    await hass.http.async_register_static_paths([
        StaticPathConfig(
            "/automation_suggestions",
            hass.config.path("custom_components/automation_suggestions/www"),
            cache_headers=False,
        )
    ])

    # ... rest of setup
```

### Phase 4: Lovelace Card

**File: `www/automation-suggestions-card.js`**

```javascript
/**
 * Automation Suggestions Card
 * Displays all automation suggestions with domain grouping, dismiss buttons, and scan trigger.
 */

const DOMAIN_EMOJI = {
  light: "💡",
  switch: "🔌",
  cover: "🚪",
  climate: "🌡️",
  scene: "🎬",
  script: "📜",
  input_number: "⚙️",
  input_boolean: "⚙️",
  input_select: "⚙️",
  input_datetime: "⚙️",
  input_button: "⚙️",
};

class AutomationSuggestionsCard extends HTMLElement {
  // Internal state
  _hass = null;
  _config = null;
  _suggestions = [];
  _total = 0;
  _page = 1;
  _pages = 0;
  _scanning = false;
  _loading = true;
  _error = null;
  _unsubscribe = null;
  _collapsedDomains = new Set();
  _boundHandleClick = null;

  // Memoization cache
  _groupedCache = null;
  _groupedCacheKey = null;

  static getStubConfig() {
    return { page_size: 20 };
  }

  setConfig(config) {
    this._config = { page_size: 20, ...config };
  }

  set hass(hass) {
    const oldHass = this._hass;
    this._hass = hass;

    // Only re-render if hass actually changed (prevents excessive renders)
    if (oldHass === null || hass.language !== oldHass.language) {
      this._render();
    }
  }

  connectedCallback() {
    // Set up event delegation
    this._boundHandleClick = this._handleClick.bind(this);
    this.addEventListener("click", this._boundHandleClick);

    // Subscribe to WebSocket updates
    this._subscribeToUpdates();
  }

  disconnectedCallback() {
    // Clean up event listeners
    if (this._boundHandleClick) {
      this.removeEventListener("click", this._boundHandleClick);
      this._boundHandleClick = null;
    }

    // Unsubscribe from WebSocket
    if (this._unsubscribe) {
      this._unsubscribe();
      this._unsubscribe = null;
    }
  }

  async _subscribeToUpdates() {
    if (!this._hass) return;

    try {
      this._unsubscribe = await this._hass.connection.subscribeMessage(
        (msg) => {
          this._suggestions = msg.suggestions || [];
          this._total = msg.total || 0;
          this._loading = false;
          this._invalidateGroupCache();
          this._render();
        },
        { type: "automation_suggestions/subscribe" }
      );
    } catch (err) {
      this._error = err.message;
      this._loading = false;
      this._render();
    }
  }

  _handleClick(event) {
    const target = event.target;

    // Dismiss button
    if (target.classList.contains("dismiss-btn")) {
      const suggestionId = target.dataset.suggestionId;
      if (suggestionId) this._dismiss(suggestionId);
      return;
    }

    // Scan Now button
    if (target.classList.contains("scan-btn")) {
      this._scanNow();
      return;
    }

    // Domain header (collapse toggle)
    if (target.classList.contains("domain-header")) {
      const domain = target.dataset.domain;
      if (domain) this._toggleDomain(domain);
      return;
    }

    // Pagination
    if (target.classList.contains("page-prev") && this._page > 1) {
      this._page--;
      this._fetchPage();
      return;
    }
    if (target.classList.contains("page-next") && this._page < this._pages) {
      this._page++;
      this._fetchPage();
      return;
    }

    // Retry button
    if (target.classList.contains("retry-btn")) {
      this._error = null;
      this._loading = true;
      this._render();
      this._subscribeToUpdates();
    }
  }

  async _dismiss(suggestionId) {
    try {
      await this._hass.callService("automation_suggestions", "dismiss", {
        suggestion_id: suggestionId,
      });
    } catch (err) {
      console.error("Failed to dismiss suggestion:", err);
    }
  }

  async _scanNow() {
    // Re-entry guard: prevent double-clicks
    if (this._scanning) return;

    this._scanning = true;
    this._render();

    try {
      await this._hass.callService("automation_suggestions", "analyze_now", {});
    } catch (err) {
      console.error("Failed to trigger scan:", err);
      this._error = "Scan failed. Please try again.";
    } finally {
      this._scanning = false;
      this._render();
    }
  }

  _toggleDomain(domain) {
    if (this._collapsedDomains.has(domain)) {
      this._collapsedDomains.delete(domain);
    } else {
      this._collapsedDomains.add(domain);
    }
    this._render();
  }

  async _fetchPage() {
    this._loading = true;
    this._render();

    try {
      const result = await this._hass.callWS({
        type: "automation_suggestions/list",
        page: this._page,
        page_size: this._config.page_size,
      });
      this._suggestions = result.suggestions;
      this._total = result.total;
      this._pages = result.pages;
      this._loading = false;
      this._invalidateGroupCache();
    } catch (err) {
      this._error = err.message;
      this._loading = false;
    }
    this._render();
  }

  _invalidateGroupCache() {
    this._groupedCache = null;
    this._groupedCacheKey = null;
  }

  _groupByDomain(suggestions) {
    // Memoization: only recompute if suggestions changed
    const cacheKey = JSON.stringify(suggestions.map((s) => s.id));
    if (this._groupedCacheKey === cacheKey && this._groupedCache) {
      return this._groupedCache;
    }

    const grouped = {};
    for (const s of suggestions) {
      const domain = s.entity_id?.split(".")[0] || "unknown";
      if (!grouped[domain]) grouped[domain] = [];
      grouped[domain].push(s);
    }

    // Sort domains by count descending
    const sorted = Object.entries(grouped).sort((a, b) => b[1].length - a[1].length);

    this._groupedCache = sorted;
    this._groupedCacheKey = cacheKey;
    return sorted;
  }

  _render() {
    if (!this._hass) return;

    // Loading state
    if (this._loading) {
      this.innerHTML = `
        <ha-card>
          <div class="card-content loading">
            <ha-circular-progress active></ha-circular-progress>
            <span>Loading suggestions...</span>
          </div>
        </ha-card>
      `;
      this._applyStyles();
      return;
    }

    // Error state
    if (this._error) {
      this.innerHTML = `
        <ha-card>
          <div class="card-content error">
            <ha-icon icon="mdi:alert-circle"></ha-icon>
            <span>${this._error}</span>
            <mwc-button class="retry-btn">Retry</mwc-button>
          </div>
        </ha-card>
      `;
      this._applyStyles();
      return;
    }

    // Empty state
    if (this._suggestions.length === 0) {
      this.innerHTML = `
        <ha-card>
          <div class="card-header">Automation Suggestions</div>
          <div class="card-content empty">
            <ha-icon icon="mdi:lightbulb-outline"></ha-icon>
            <span>No suggestions yet.</span>
            <mwc-button class="scan-btn" ${this._scanning ? "disabled" : ""}>
              ${this._scanning ? "Scanning..." : "Scan Now"}
            </mwc-button>
          </div>
        </ha-card>
      `;
      this._applyStyles();
      return;
    }

    // Main content
    const grouped = this._groupByDomain(this._suggestions);

    let domainsHtml = "";
    for (const [domain, suggestions] of grouped) {
      const emoji = DOMAIN_EMOJI[domain] || "📋";
      const isCollapsed = this._collapsedDomains.has(domain);
      const collapseIcon = isCollapsed ? "mdi:chevron-right" : "mdi:chevron-down";

      let suggestionsHtml = "";
      if (!isCollapsed) {
        for (const s of suggestions) {
          const name = s.friendly_name || s.entity_id;
          const action = (s.action || "").replace(/_/g, " ");
          const pct = Math.round((s.consistency_score || 0) * 100);
          suggestionsHtml += `
            <div class="suggestion">
              <div class="suggestion-main">
                <span class="action">${action}</span>
                <span class="name">${name}</span>
                <span class="time">around ${s.suggested_time}</span>
              </div>
              <div class="suggestion-meta">
                ${pct}% consistent, seen ${s.occurrence_count} times
              </div>
              <mwc-icon-button class="dismiss-btn" data-suggestion-id="${s.id}" title="Dismiss">
                <ha-icon icon="mdi:close"></ha-icon>
              </mwc-icon-button>
            </div>
          `;
        }
      }

      domainsHtml += `
        <div class="domain-section">
          <div class="domain-header" data-domain="${domain}">
            <ha-icon icon="${collapseIcon}"></ha-icon>
            <span class="domain-emoji">${emoji}</span>
            <span class="domain-name">${domain.replace(/_/g, " ")}</span>
            <span class="domain-count">(${suggestions.length})</span>
          </div>
          <div class="domain-suggestions ${isCollapsed ? "collapsed" : ""}">
            ${suggestionsHtml}
          </div>
        </div>
      `;
    }

    // Pagination
    let paginationHtml = "";
    if (this._pages > 1) {
      paginationHtml = `
        <div class="pagination">
          <mwc-icon-button class="page-prev" ${this._page <= 1 ? "disabled" : ""}>
            <ha-icon icon="mdi:chevron-left"></ha-icon>
          </mwc-icon-button>
          <span>Page ${this._page} of ${this._pages}</span>
          <mwc-icon-button class="page-next" ${this._page >= this._pages ? "disabled" : ""}>
            <ha-icon icon="mdi:chevron-right"></ha-icon>
          </mwc-icon-button>
        </div>
      `;
    }

    this.innerHTML = `
      <ha-card>
        <div class="card-header">
          Automation Suggestions
          <span class="total-count">(${this._total} total)</span>
        </div>
        <div class="card-content">
          ${domainsHtml}
        </div>
        <div class="card-actions">
          <mwc-button class="scan-btn" ${this._scanning ? "disabled" : ""}>
            ${this._scanning ? "Scanning..." : "🔄 Scan Now"}
          </mwc-button>
          ${paginationHtml}
        </div>
      </ha-card>
    `;
    this._applyStyles();
  }

  _applyStyles() {
    // Only add styles once
    if (this.querySelector("style")) return;

    const style = document.createElement("style");
    style.textContent = `
      ha-card {
        padding: 0;
      }
      .card-header {
        padding: 16px;
        font-size: 1.2em;
        font-weight: 500;
        border-bottom: 1px solid var(--divider-color);
      }
      .total-count {
        font-size: 0.8em;
        color: var(--secondary-text-color);
        font-weight: normal;
      }
      .card-content {
        padding: 8px 16px;
      }
      .card-content.loading,
      .card-content.empty,
      .card-content.error {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 16px;
        padding: 32px;
        text-align: center;
        color: var(--secondary-text-color);
      }
      .domain-section {
        margin-bottom: 8px;
      }
      .domain-header {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px;
        cursor: pointer;
        border-radius: 4px;
        font-weight: 500;
      }
      .domain-header:hover {
        background: var(--secondary-background-color);
      }
      .domain-count {
        color: var(--secondary-text-color);
        font-weight: normal;
      }
      .domain-suggestions.collapsed {
        display: none;
      }
      .suggestion {
        display: grid;
        grid-template-columns: 1fr auto;
        grid-template-rows: auto auto;
        gap: 4px;
        padding: 8px 8px 8px 40px;
        border-bottom: 1px solid var(--divider-color);
      }
      .suggestion:last-child {
        border-bottom: none;
      }
      .suggestion-main {
        grid-column: 1;
        grid-row: 1;
      }
      .suggestion-meta {
        grid-column: 1;
        grid-row: 2;
        font-size: 0.85em;
        color: var(--secondary-text-color);
      }
      .dismiss-btn {
        grid-column: 2;
        grid-row: 1 / span 2;
        align-self: center;
        --mdc-icon-button-size: 36px;
      }
      .action {
        text-transform: capitalize;
      }
      .card-actions {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 16px;
        border-top: 1px solid var(--divider-color);
      }
      .pagination {
        display: flex;
        align-items: center;
        gap: 8px;
      }
    `;
    this.prepend(style);
  }

  getCardSize() {
    return 3;
  }
}

customElements.define("automation-suggestions-card", AutomationSuggestionsCard);

// Register for card picker (optional)
window.customCards = window.customCards || [];
window.customCards.push({
  type: "automation-suggestions-card",
  name: "Automation Suggestions",
  description: "View and manage automation suggestions",
});
```

### Card YAML Config

```yaml
type: custom:automation-suggestions-card
page_size: 20  # optional, default 20
```

### User Installation Steps (for docs)

1. Go to **Settings → Dashboards → Resources**
2. Add resource: `/automation_suggestions/automation-suggestions-card.js` (JavaScript module)
3. Add card to dashboard:
   ```yaml
   type: custom:automation-suggestions-card
   ```

## Open Questions (Resolved)

| Question | Decision |
|----------|----------|
| How does card access all suggestions? | ~~Sensor exposes all in attributes~~ **WebSocket API** |
| Pagination or infinite scroll? | Pagination with configurable page_size |
| Domains collapsed by default? | All expanded |
| Dismiss feedback? | Silent removal (real-time via WebSocket) |
| Visual card editor? | YAML-only for V1 |
| 16KB attribute limit? | **Avoided by using WebSocket API** |

## Dependencies & Risks

| Risk | Mitigation |
|------|------------|
| ~~Large JSON in sensor state~~ | **Eliminated**: WebSocket API with pagination |
| Card not loading ("Custom element doesn't exist") | Clear documentation + static path testing |
| Service call failures | Card shows error state with retry button |
| Race conditions (double-click scan) | Re-entry guard in `_scanNow()` |
| Memory leaks from listeners | `disconnectedCallback` cleanup |
| Excessive re-renders | State change detection in `set hass()` |

## Success Metrics

- Users can view all suggestions (not just 5)
- Reddit feedback: no more "can only see top 5" complaints
- Card works in light/dark themes
- Dismiss and Scan Now work reliably
- No performance issues with 100+ suggestions

## Alternative: Quick V0.5 Release

For users who want a quick solution before the full card is ready, document a **Markdown card with Jinja template** approach:

```yaml
type: markdown
title: Top Suggestions
content: |
  {% set suggestions = state_attr('sensor.automation_suggestions_top', 'suggestions') %}
  {% if suggestions %}
    {% for s in suggestions %}
  - **{{ s.action | replace('_', ' ') | title }}** {{ s.friendly_name or s.entity_id }} around {{ s.suggested_time }}
    _{{ (s.consistency_score * 100) | round }}% consistent, seen {{ s.occurrence_count }} times_
    {% endfor %}
  {% else %}
  No suggestions yet. Run the analyze service to scan for patterns.
  {% endif %}
```

This provides an immediate 80% solution while the full card is developed.

## References

- Brainstorm: `docs/brainstorms/2026-01-24-view-all-suggestions-brainstorm.md`
- Current sensor: `custom_components/automation_suggestions/sensor.py:112-149`
- Current notifications: `custom_components/automation_suggestions/coordinator.py:208-258`
- Services: `custom_components/automation_suggestions/services.py`
- HA Custom Card Tutorial: https://developers.home-assistant.io/docs/frontend/custom-ui/custom-card
- HA WebSocket API: https://developers.home-assistant.io/docs/api/websocket
- HA State Attribute Limits: Discovered via architecture review (16KB hard limit)
