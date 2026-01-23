# Brainstorm: Automation Suggestions Integration

**Date:** 2026-01-23
**Status:** Complete
**Source PRD:** `docs/PRD-automation-suggestions-integration.md`

## What We're Building

A **Home Assistant custom integration** that runs the `extract_manual_actions.py` pattern analysis automatically and exposes suggestions as native HA sensors.

**Key question resolved:** Integration vs Add-on → **Integration** because:
- Direct access to logbook/recorder APIs (no REST overhead)
- Works on ALL HA installations (Core, Container, HAOS, Supervised)
- Native sensor/service creation
- Precedent: AI Automation Suggester uses same pattern

## Why This Approach

### Integration over Add-on

| Factor | Integration | Add-on |
|--------|-------------|--------|
| HA installation types | All | HAOS/Supervised only |
| Data access | Direct Python APIs | REST API with auth |
| Sensor creation | Native | Would need MQTT bridge |
| Distribution | HACS | Add-on Store |
| Similar projects | AI Automation Suggester | None found |

Community feedback explicitly asked for "an integration that regularly looks for these things."

### Simplified V1 Scope

Based on discussion, V1 focuses on **discovery only**:
- No YAML generation
- No auto-creation of automations
- Just surface patterns and let users act on them manually

This follows YAGNI—prove value before adding complexity.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Integration vs Add-on | **Integration** | Universal compatibility, direct API access |
| User filtering | **Single-user** | Simplicity; filter by `context_user_id` presence only |
| Lovelace card | **Not in V1** | Users can build own views; ship core first |
| YAML generation | **Not in V1** | Just suggest, don't generate code |
| Notifications | **Persistent notification** | Works everywhere, simple implementation |

## V1 Feature Set

### Included
- Scheduled analysis (weekly or bi-weekly, configurable)
- `sensor.automation_suggestions_count` - number of suggestions
- `sensor.automation_suggestions_top` - JSON array of top candidates
- `binary_sensor.automation_suggestions_available` - quick check
- `automation_suggestions.analyze_now` service - on-demand analysis
- `automation_suggestions.dismiss` service - hide a suggestion
- Persistent notification when new high-confidence patterns found

### Domains to Track

| Domain | Examples | Pattern Type |
|--------|----------|--------------|
| `light` | Ceiling light, lamp | on/off/brightness |
| `switch` | Smart plug, relay | on/off |
| `cover` | Blinds, garage door | open/close/position |
| `climate` | Thermostat, AC | mode/temperature |
| `scene` | Movie night, Good morning | activation |
| `script` | Custom sequences | execution |
| `input_number` | Temp setpoint, brightness preset | value changes |
| `input_boolean` | Guest mode, vacation mode | toggle |
| `input_select` | House mode, HVAC mode | selection |
| `input_datetime` | Wake time, bedtime | time changes |
| `input_button` | Manual triggers | presses |

**Note:** Current script only covers light, switch, scene, cover, climate, script. V1 integration should expand to include input_* helpers.

### Deferred to V2+
- Per-user pattern breakdown
- Lovelace card
- YAML generation
- Auto-creation via HA API
- Configurable notification targets
- Weekly digest notifications

## Technical Notes

- Port `extract_manual_actions.py` logic to async Python
- Use `DataUpdateCoordinator` with configurable interval (default: 7 days)
- Analyze 14-28 days of logbook data to catch weekly patterns
- Use HA's `Store` helper for persisting dismissed items
- Access logbook via `homeassistant.components.logbook` internals
- Run analysis in executor to avoid blocking event loop

## Open Questions

1. **Minimum HA version?** PRD says 2024.1+ for modern config flow—confirm this is still accurate
2. **HACS category?** Likely "Integration" not "Plugin"

## Community Input (from blog feedback)

- User requested per-user filtering → deferred to V2
- Explicit request for "integration like Alexa hunches" → validates approach
- Interest in the script itself → market exists

## Vision: End-to-End Automation Pipeline

The long-term goal is a **fully autonomous automation pipeline** that runs end-to-end without human input:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   1. DETECT     │────▶│   2. GENERATE   │────▶│   3. IMPLEMENT  │────▶│   4. MONITOR    │
│                 │     │                 │     │                 │     │                 │
│ Pattern analysis│     │ AI creates      │     │ Claude Code +   │     │ Track if        │
│ on 2-4 weeks of │     │ automation      │     │ ha-mcp writes   │     │ automation      │
│ logbook data    │     │ suggestions     │     │ the automation  │     │ is effective    │
│                 │     │                 │     │                 │     │                 │
│    [Auto]       │     │    [Auto]       │     │    [Auto]       │     │    [Auto]       │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
                                                 Self-correcting:
                                              disables bad automations,
                                              refines based on feedback
```

**North star:** Your home learns and adapts without you lifting a finger. The system observes your habits, creates automations, and self-corrects when they don't work.

### Data Sources (Evolving Home)

A truly evolving home needs multiple data inputs:

| Source | Type | What It Captures | Example Pattern |
|--------|------|------------------|-----------------|
| **Manual actions** | Behavior | What you do | "Lights on at 7am daily" |
| **Sensor readings** | Environment | What's happening | "Motion in kitchen at 7am" |
| **Entity capabilities** | Potential | What's possible | "Motion sensor + lights exist" |
| **State correlations** | Context | What coincides | "Lights on when motion detected" |

**V1:** Manual actions only (prove the pipeline works)
**V2+:** Add sensor correlation (find triggers for manual actions)
**Vision:** All sources combined (truly autonomous home)

**Example evolution:**
1. Detect: "You turn on kitchen lights at 7am daily"
2. Correlate: "Motion sensor fires at 6:58am on those days"
3. Generate: "Turn on kitchen lights when motion detected between 6:30-7:30am"
4. Implement: Automation created
5. Monitor: User stops manually turning on lights → success
6. Refine: Extend time window based on weekend patterns

### Self-Correcting Feedback Loop

The system learns from human corrections, not just patterns:

| User Action | System Interpretation | Response |
|-------------|----------------------|----------|
| Disables automation | "This was wrong" | Log reason, don't recreate similar |
| Adjusts time window | "Right idea, wrong timing" | Update automation, learn new window |
| Changes brightness/temp value | "Right trigger, wrong value" | Adjust and monitor if new value sticks |
| Manually overrides shortly after trigger | "Automation fired at wrong moment" | Narrow conditions or add exclusions |
| Re-enables after disabling | "Changed mind / context changed" | Restore and monitor |

**Correction detection (in analysis loop):**
- Compare automation's `last_triggered` vs manual actions on same entity
- Track automation enable/disable state changes
- Diff automation YAML between runs to detect value adjustments
- Monitor for manual overrides within N minutes of automation trigger

**Learning outcomes:**
- Adjust confidence thresholds per entity/pattern type
- Build "don't automate" list for patterns that keep getting rejected
- Refine time windows, values, conditions based on corrections
- Identify context gaps (e.g., "works weekdays but not weekends")

### How This Differs from AI Automation Suggester

| Aspect | AI Automation Suggester | This Pipeline |
|--------|------------------------|---------------|
| **Input** | Current entity state | **Historical behavior patterns** |
| **Question answered** | "What *could* you automate?" | "What *do* you keep doing manually?" |
| **Basis** | Speculative (device capabilities) | **Evidence-based** (your actual habits) |
| **External deps** | Requires LLM provider | V1: None. Vision: LLM for generation |
| **End state** | Suggestion notification | **Implemented automation** |

They're complementary: AI Suggester explores possibilities, this catches habits.

### Pipeline Stages (Future)

1. **Detect** (V1) - Pattern analysis on 2-4 weeks of logbook data. Longer timeframe than daily to catch weekly patterns.
2. **Generate** (V2) - Feed detected patterns to LLM to generate automation YAML. Could integrate with AI Suggester or custom prompting.
3. **Implement** (V3) - Claude Code with ha-mcp writes automations to config. Human approval required.
4. **Monitor** (V3+) - Track if created automations are actually used or get disabled.

### Implementation Options (Stage 3)

Several options exist for the Claude Code implementation stage:

| Option | Repo | Pros | Cons |
|--------|------|------|------|
| **Local Claude Code + ha-mcp** | Current setup | Full control, no extra infra, already working | Requires dev machine running |
| **heytcass add-on** | [heytcass/home-assistant-addons](https://github.com/heytcass/home-assistant-addons) | Runs on HA device, terminal in dashboard | Basic, original version |
| **ESJavadex add-on** | [ESJavadex/claude-code-ha](https://github.com/ESJavadex/claude-code-ha) | Enhanced fork, image support, persistent packages | Still requires manual interaction |
| **philippb system** | [philippb/claude-homeassistant](https://github.com/philippb/claude-homeassistant) | Full validation hooks, automated testing, natural language | Most complex setup |
| **danbuhler CLI** | [danbuhler/claude-code-ha](https://github.com/danbuhler/claude-code-ha) | Simple CLI tools, natural language commands | Less integrated |

**Current recommendation:** Stay with local Claude Code + ha-mcp for now. It's already working and gives full control. Evaluate add-ons when we reach V3 implementation stage.

### Trust Ladder

Early versions use approval gates while building confidence. Long-term: fully autonomous.

| Version | Autonomy Level | Human Involvement |
|---------|----------------|-------------------|
| V1 | Detection only | Human reviews patterns, acts manually |
| V2 | Detect + Generate | Human approves before implementation |
| V3 | Full pipeline | Human can intervene, but not required |
| V4+ | Self-correcting | System monitors and adjusts autonomously |

**Safety mechanisms for autonomous mode:**
- High confidence threshold (90%+) before auto-implementing
- New automations start disabled, enabled after human doesn't object within 24h
- Auto-disable if automation triggers but user manually overrides within 5 min
- Weekly digest of changes for awareness (not approval)

## Next Steps

Run `/workflows:plan` to create implementation plan for the V1 custom integration (pattern detection only).
