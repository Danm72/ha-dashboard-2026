---
title: "pytest-homeassistant-custom-component blocks sockets for Docker/testcontainers"
date: 2026-01-23
category: testing
tags:
  - pytest
  - homeassistant
  - docker
  - testcontainers
  - e2e
  - pytest-socket
module: tests/e2e
symptoms:
  - "pytest_socket.SocketConnectBlockedError: A test tried to use socket.socket.connect()"
  - "testcontainers fails to connect to Docker daemon"
  - "Session-scoped fixtures fail before test hooks can enable sockets"
  - "E2E tests fail with socket connection blocked errors"
root_cause: "Plugin registers as 'homeassistant' entry point, not 'homeassistant-custom-component'"
---

# pytest-homeassistant-custom-component Blocks Sockets

## Problem

E2E tests using Docker/testcontainers fail with socket blocked errors:

```
pytest_socket.SocketConnectBlockedError: A test tried to use socket.socket.connect()
with host "None" (allowed: "127.0.0.1")
```

## Root Cause

`pytest-homeassistant-custom-component` uses `pytest-socket` to block network connections for test isolation. The plugin registers with an **unexpected entry point name**.

**Key Discovery**: Check `entry_points.txt`:
```
[pytest11]
homeassistant = pytest_homeassistant_custom_component.plugins
```

The plugin name is `homeassistant`, NOT `homeassistant-custom-component` or `pytest-homeassistant-custom-component`.

## What Doesn't Work

| Approach | Why It Fails |
|----------|--------------|
| `pytest_runtest_setup` hook with `socket.enable()` | Session fixtures run BEFORE this hook |
| `pytest_configure` hook | Plugin already loaded |
| `-p no:homeassistant-custom-component` | Wrong plugin name |
| `-p no:socket` | HA plugin re-disables sockets |
| `--force-enable-socket` | Plugin overrides it |

## Solution

Create `tests/e2e/pytest.ini`:

```ini
[pytest]
# Disable the homeassistant plugin to allow socket access for Docker/testcontainers
# NOTE: Entry point is "homeassistant", not "homeassistant-custom-component"
addopts =
    -p no:homeassistant
    --strict-markers
    -v
    --tb=short

markers =
    e2e: marks tests as end-to-end (requires Docker)
    live_only: marks tests as requiring a live Home Assistant instance

pythonpath = ../..
asyncio_mode = auto
```

Run e2e tests with:
```bash
pytest tests/e2e/ -c tests/e2e/pytest.ini
```

## Why This Works

1. `-p no:homeassistant` disables the plugin during initialization
2. Plugin never loads → `pytest-socket` never blocks connections
3. testcontainers can freely communicate with Docker

## Directory Structure

```
project/
├── conftest.py                    # Minimal - no plugin loading
├── custom_components/
│   └── integration/
│       └── tests/
│           └── integration/
│               └── conftest.py    # pytest_plugins = ["pytest_homeassistant_custom_component"]
└── tests/
    └── e2e/
        ├── pytest.ini             # addopts = -p no:homeassistant
        └── conftest.py            # Docker/testcontainers fixtures
```

## Quick Diagnostic

Find any pytest plugin's actual name:
```bash
cat $(pip show -f PACKAGE | grep Location | cut -d' ' -f2)/PACKAGE*.dist-info/entry_points.txt
```

## Prevention

- Always check `entry_points.txt` for plugin names, not package names
- Keep e2e tests in separate directory with dedicated `pytest.ini`
- Document the `-c` flag requirement in README

## Related Files

- `tests/e2e/pytest.ini` - E2E test configuration
- `tests/e2e/conftest.py` - Docker/testcontainers fixtures
- `custom_components/automation_suggestions/tests/integration/conftest.py` - Integration tests (loads plugin)
