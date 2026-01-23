# E2E Tests

End-to-end tests using real Home Assistant Docker containers.

## Prerequisites

```bash
pip install testcontainers requests docker
```

## Initial Setup (One-time)

To run authenticated tests, you need to create a test token:

1. Start a Home Assistant container manually:
   ```bash
   docker run -d -p 8123:8123 ghcr.io/home-assistant/home-assistant:stable
   ```

2. Complete onboarding at http://localhost:8123

3. Create a long-lived access token:
   - Go to Profile -> Security -> Long-lived access tokens
   - Create token named "E2E Tests"
   - Copy the token

4. Copy the `.storage/` directory to `tests/e2e/initial_test_state/`

5. Set the token as environment variable:
   ```bash
   export HA_TEST_TOKEN="your_token_here"
   ```

## Running Tests

```bash
# Run e2e tests (skips auth tests if token not set)
pytest tests/e2e/ -v -m e2e

# Run all tests except e2e
pytest -m "not e2e"
```

## What These Tests Catch

- API compatibility issues (like `session_scope` deprecation)
- Integration loading problems
- Real recorder/logbook behavior
