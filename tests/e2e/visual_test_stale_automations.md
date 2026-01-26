# Visual E2E Tests: Stale Automation Detection

This document defines visual E2E tests for the stale automation detection feature's Lovelace card interface. These tests are designed to be run interactively using Claude Chrome MCP browser automation tools.

## Prerequisites

### 1. Start the Test Environment

Start the Home Assistant Docker container with the custom component installed:

```bash
cd /Users/dan/dev/homeassist/ha-dashboard-2026-public
python tests/e2e/start_visual_test.py
```

This will output the URL (e.g., `http://localhost:32768`). Note this URL for the tests.

### 2. Complete Home Assistant Onboarding

If this is a fresh container, complete onboarding:
- Create account: username `test`, password `test`
- Skip integrations setup

### 3. Configure the Automation Suggestions Integration

1. Navigate to **Settings > Devices & Services**
2. Click **Add Integration**
3. Search for "Automation Suggestions"
4. Complete the configuration with default values

### 4. Add the Card Resource

1. Navigate to **Settings > Dashboards > Resources** (or three-dot menu > Resources)
2. Click **Add Resource**
3. URL: `/local/custom_components/automation_suggestions/www/automation-suggestions-card.js`
4. Resource type: JavaScript module

### 5. Create a Dashboard with the Card

1. Navigate to **Overview** dashboard
2. Click three-dot menu > **Edit Dashboard** > **Take Control**
3. Click **Add Card**
4. Select "Custom: Automation Suggestions" or use YAML:
   ```yaml
   type: custom:automation-suggestions-card
   ```

### 6. Create Test Automations

To test stale automation detection, create several test automations with varying states:

#### Active Automation (triggered recently)
```yaml
alias: Test Active Automation
trigger:
  - platform: time
    at: "00:00:00"
action:
  - service: logger.log
    data:
      message: "Test"
mode: single
```

#### Stale Automation (never triggered)
```yaml
alias: Test Stale Never Triggered
trigger:
  - platform: event
    event_type: nonexistent_event
action:
  - service: logger.log
    data:
      message: "Never runs"
mode: single
```

#### Disabled Automation
Create an automation and disable it via the UI or:
```yaml
alias: Test Disabled Automation
trigger:
  - platform: time
    at: "23:59:59"
action:
  - service: logger.log
    data:
      message: "Disabled"
mode: single
```
Then disable it via **Settings > Automations & Scenes**, find the automation, and toggle off.

---

## Test Cases

### Test 1: Card Loads with Tabs Visible

**Objective:** Verify the card renders with both "Suggestions" and "Stale" tabs.

**Preconditions:**
- Card is added to dashboard
- Integration is configured

**Steps:**

1. Navigate to the dashboard containing the automation-suggestions-card
   ```
   Chrome MCP: mcp__claude-in-chrome__navigate
   URL: http://localhost:<port>/lovelace/0
   ```

2. Wait for page to load (2-3 seconds)

3. Take a screenshot to capture card state
   ```
   Chrome MCP: mcp__claude-in-chrome__computer
   action: screenshot
   ```

4. Read the page to find tab elements
   ```
   Chrome MCP: mcp__claude-in-chrome__read_page
   ```

**Expected Results:**
- Card displays with header "Automation Suggestions"
- Two tab buttons are visible: "Suggestions (N)" and "Stale (N)"
- "Suggestions" tab is active by default (highlighted with primary color border)
- Both tabs show count badges in parentheses
- Card content area shows suggestions list or empty state

**Verification Queries:**
- Look for elements with class `tab-btn`
- Verify `tab-btn.active` exists and contains "Suggestions"
- Verify both tabs display count numbers

---

### Test 2: Clicking Stale Tab Shows Stale Automations List

**Objective:** Verify clicking the "Stale" tab switches content to show stale automations.

**Preconditions:**
- Card is loaded on dashboard
- At least one stale automation exists (either never triggered or not triggered within threshold)

**Steps:**

1. Navigate to dashboard if not already there
   ```
   Chrome MCP: mcp__claude-in-chrome__navigate
   URL: http://localhost:<port>/lovelace/0
   ```

2. Click the "Stale" tab
   ```
   Chrome MCP: mcp__claude-in-chrome__computer
   action: click
   coordinate: [x, y] (center of Stale tab button)
   ```

   Alternative using find:
   ```
   Chrome MCP: mcp__claude-in-chrome__find
   query: "Stale"
   action: click
   ```

3. Take a screenshot
   ```
   Chrome MCP: mcp__claude-in-chrome__computer
   action: screenshot
   ```

4. Read the page content
   ```
   Chrome MCP: mcp__claude-in-chrome__read_page
   ```

**Expected Results:**
- "Stale" tab becomes active (highlighted)
- "Suggestions" tab becomes inactive
- Content area displays list of stale automations
- Each stale automation shows:
  - Automation name
  - Last triggered date or "Never"
  - Days since triggered

**Verification Queries:**
- Verify `tab-btn.active` now contains "Stale"
- Look for `.stale-item` elements in the DOM
- Verify automation names are displayed

---

### Test 3: Stale Automation Displays Name, Last Triggered Date, and Days Since

**Objective:** Verify each stale automation item shows correct details.

**Preconditions:**
- Stale tab is active
- At least one stale automation exists

**Steps:**

1. Ensure on Stale tab (repeat Test 2 steps if needed)

2. Read page to examine stale item structure
   ```
   Chrome MCP: mcp__claude-in-chrome__read_page
   ```

3. Take a detailed screenshot
   ```
   Chrome MCP: mcp__claude-in-chrome__computer
   action: screenshot
   ```

**Expected Results:**
For each stale automation item (`.stale-item`):
- `.stale-name` contains the automation's friendly name
- `.stale-meta` shows "Last triggered: [date] ([N] days ago)" format
- If automation never triggered: "Last triggered: Never (Never triggered)"
- Layout: name on first line, metadata on second line, dismiss button on right

**Sample Expected HTML Structure:**
```html
<div class="stale-item">
  <div class="stale-main">
    <span class="stale-name">Test Stale Never Triggered</span>
  </div>
  <div class="stale-meta">
    Last triggered: Never (Never triggered)
  </div>
  <button class="dismiss-btn" data-suggestion-id="automation.test_stale_never_triggered">
    <ha-icon icon="mdi:close"></ha-icon>
  </button>
</div>
```

---

### Test 4: Disabled Automations Show Disabled Badge

**Objective:** Verify disabled automations display a "Disabled" badge.

**Preconditions:**
- Stale tab is active
- At least one disabled automation exists that is also stale

**Steps:**

1. Ensure Stale tab is active

2. Read page to find disabled badge
   ```
   Chrome MCP: mcp__claude-in-chrome__read_page
   ```

3. Take screenshot capturing the disabled badge
   ```
   Chrome MCP: mcp__claude-in-chrome__computer
   action: screenshot
   ```

**Expected Results:**
- Disabled stale automations have an orange badge with text "DISABLED"
- Badge appears next to the automation name in `.stale-main`
- Badge uses class `badge disabled`
- Badge styling: orange background (`--warning-color`), white text, uppercase

**Sample Expected HTML:**
```html
<div class="stale-main">
  <span class="stale-name">Test Disabled Automation</span>
  <span class="badge disabled">Disabled</span>
</div>
```

---

### Test 5: Dismiss Button Removes Automation from List

**Objective:** Verify clicking the dismiss button removes the automation from the stale list.

**Preconditions:**
- Stale tab is active
- At least one stale automation is displayed

**Steps:**

1. Note the current count in the Stale tab badge
   ```
   Chrome MCP: mcp__claude-in-chrome__read_page
   ```

2. Find and note the first stale automation's name

3. Click the dismiss button (X icon) for the first automation
   ```
   Chrome MCP: mcp__claude-in-chrome__computer
   action: click
   coordinate: [x, y] (center of dismiss button)
   ```

   Alternative approach - use JavaScript:
   ```
   Chrome MCP: mcp__claude-in-chrome__javascript_tool
   script: document.querySelector('.stale-item .dismiss-btn').click()
   ```

4. Wait for WebSocket update (500ms)

5. Take a screenshot
   ```
   Chrome MCP: mcp__claude-in-chrome__computer
   action: screenshot
   ```

6. Read page to verify removal
   ```
   Chrome MCP: mcp__claude-in-chrome__read_page
   ```

**Expected Results:**
- Dismissed automation no longer appears in the list
- Stale tab badge count decreases by 1
- Other stale automations remain visible
- No error messages displayed

---

### Test 6: Empty State Displays Correctly When No Stale Automations

**Objective:** Verify the empty state message when all stale automations are dismissed or none exist.

**Preconditions:**
- Stale tab is active
- No stale automations exist (or all have been dismissed)

**Steps:**

1. If stale automations exist, dismiss all of them (repeat Test 5)

2. Once list is empty, take screenshot
   ```
   Chrome MCP: mcp__claude-in-chrome__computer
   action: screenshot
   ```

3. Read page content
   ```
   Chrome MCP: mcp__claude-in-chrome__read_page
   ```

**Expected Results:**
- Content area shows centered empty state
- Checkmark icon (`mdi:check-circle`) is displayed
- Primary text: "No stale automations found."
- Secondary hint text: "All your automations have triggered within the threshold."
- Stale tab badge shows "(0)"

**Sample Expected HTML:**
```html
<div class="card-content empty">
  <ha-icon icon="mdi:check-circle"></ha-icon>
  <span>No stale automations found.</span>
  <span class="empty-hint">All your automations have triggered within the threshold.</span>
</div>
```

---

### Test 7: Tab Switching Works Correctly Between Suggestions and Stale

**Objective:** Verify smooth tab switching in both directions without content corruption.

**Preconditions:**
- Card is loaded with some suggestions and/or stale automations

**Steps:**

1. Start on Suggestions tab (default)

2. Take initial screenshot
   ```
   Chrome MCP: mcp__claude-in-chrome__computer
   action: screenshot
   ```

3. Click Stale tab
   ```
   Chrome MCP: mcp__claude-in-chrome__find
   query: "Stale"
   action: click
   ```

4. Take screenshot of Stale tab
   ```
   Chrome MCP: mcp__claude-in-chrome__computer
   action: screenshot
   ```

5. Click Suggestions tab
   ```
   Chrome MCP: mcp__claude-in-chrome__find
   query: "Suggestions"
   action: click
   ```

6. Take screenshot showing return to Suggestions
   ```
   Chrome MCP: mcp__claude-in-chrome__computer
   action: screenshot
   ```

7. Rapidly switch tabs 3 times
   ```
   Chrome MCP: mcp__claude-in-chrome__javascript_tool
   script: |
     const tabs = document.querySelectorAll('.tab-btn');
     for (let i = 0; i < 3; i++) {
       setTimeout(() => tabs[1].click(), i * 200);
       setTimeout(() => tabs[0].click(), i * 200 + 100);
     }
   ```

8. Wait 1 second, take final screenshot

**Expected Results:**
- Tab switching is immediate (no loading indicators)
- Active tab styling updates correctly each switch
- Content area updates to match selected tab
- No content "flashing" or corruption during rapid switches
- Scan Now button remains visible in card actions regardless of tab
- Tab counts remain accurate after switching

---

## Additional Verification Points

### CSS Styling Verification

Use these JavaScript queries to verify styling is applied correctly:

```javascript
// Check tab styling
const activeTab = document.querySelector('.tab-btn.active');
const computedStyle = getComputedStyle(activeTab);
console.log('Border color:', computedStyle.borderBottomColor); // Should be primary-color

// Check stale item layout
const staleItem = document.querySelector('.stale-item');
if (staleItem) {
  const gridStyle = getComputedStyle(staleItem);
  console.log('Grid template:', gridStyle.gridTemplateColumns); // Should be "1fr auto"
}

// Check badge styling
const badge = document.querySelector('.badge.disabled');
if (badge) {
  const badgeStyle = getComputedStyle(badge);
  console.log('Badge background:', badgeStyle.backgroundColor); // Should be warning-color
}
```

### WebSocket Subscription Verification

Verify the WebSocket connection is active:

```javascript
// In browser console
console.log('Suggestions:', document.querySelector('automation-suggestions-card')._suggestions);
console.log('Stale:', document.querySelector('automation-suggestions-card')._staleAutomations);
console.log('Active tab:', document.querySelector('automation-suggestions-card')._activeTab);
```

---

## Troubleshooting

### Card Not Loading

1. Check browser console for errors
2. Verify resource is registered correctly
3. Ensure integration is configured
4. Check WebSocket connection in Network tab

### Stale Tab Shows 0 When Automations Exist

1. Verify automations are truly stale (check `last_triggered` attribute in Developer Tools > States)
2. Check stale threshold setting in integration options
3. Verify automations are not in ignore patterns

### Dismiss Not Working

1. Check browser console for service call errors
2. Verify `automation_suggestions.dismiss` service is registered
3. Check that `data-suggestion-id` attribute is set correctly

---

## Test Data Reset

To reset test data between test runs:

1. Stop the container (press Enter in start_visual_test.py terminal)
2. Restart with `python tests/e2e/start_visual_test.py`
3. Repeat prerequisites setup

Or to clear dismissed items without restart:

```javascript
// Clear storage (requires HA restart to take effect)
// Via Developer Tools > Services:
// Service: automation_suggestions.analyze_now
```
