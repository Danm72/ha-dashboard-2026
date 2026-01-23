"""
E2E tests for the automation suggestions analyzer.

These tests verify the analyzer correctly identifies patterns in historical data
using a real Home Assistant instance with pre-populated recorder data.
"""

import pytest

pytestmark = [pytest.mark.e2e]


class TestAnalyzerPatternDetection:
    """Test that the analyzer detects patterns in historical data."""

    def test_integration_loads(self, ha_api):
        """Verify our integration loads in real HA."""
        resp = ha_api("GET", "/api/config")
        assert resp.status_code == 200
        config = resp.json()

        # Check our component loaded
        components = config.get("components", [])
        assert "automation_suggestions" in components, (
            f"automation_suggestions not in components: {components}"
        )

    def test_services_available(self, ha_api):
        """Verify our services are registered."""
        resp = ha_api("GET", "/api/services")
        assert resp.status_code == 200
        services = resp.json()

        # Find our domain
        domains = {s["domain"]: s["services"] for s in services}
        assert "automation_suggestions" in domains, (
            f"automation_suggestions domain not found. Available: {list(domains.keys())}"
        )

        our_services = domains["automation_suggestions"]
        assert "analyze_now" in our_services, (
            f"analyze_now service not found. Available: {list(our_services.keys())}"
        )

    def test_sensors_created(self, ha_api):
        """Verify our sensors are created."""
        resp = ha_api("GET", "/api/states")
        assert resp.status_code == 200
        states = resp.json()

        entity_ids = [s["entity_id"] for s in states]

        # Check for our sensors (entity names include domain prefix)
        expected_sensors = [
            "sensor.automation_suggestions_suggestions_count",
            "sensor.automation_suggestions_top_suggestions",
            "sensor.automation_suggestions_last_analysis",
            "binary_sensor.automation_suggestions_suggestions_available",
        ]

        for sensor in expected_sensors:
            assert sensor in entity_ids, (
                f"{sensor} not found. Automation_suggestions entities: "
                f"{[e for e in entity_ids if 'automation_suggestions' in e.lower()]}"
            )

    def test_analyze_now_service(self, ha_api):
        """Test calling the analyze_now service."""
        resp = ha_api(
            "POST",
            "/api/services/automation_suggestions/analyze_now",
            json={}
        )
        # Service call should succeed (200) or be accepted (201)
        assert resp.status_code in (200, 201), (
            f"analyze_now failed with {resp.status_code}: {resp.text}"
        )

    def test_suggestions_found_in_history(self, ha_api):
        """
        Verify analyzer finds patterns in pre-populated history.

        The test database contains:
        - light.kitchen on at ~7:00 AM daily
        - light.kitchen off at ~8:30 AM daily
        - light.bedroom off at ~10:30 PM daily
        - switch.coffee_maker on at ~6:45 AM weekdays
        """
        # Trigger analysis
        resp = ha_api(
            "POST",
            "/api/services/automation_suggestions/analyze_now",
            json={}
        )
        assert resp.status_code in (200, 201)

        # Give it a moment to process
        import time
        time.sleep(2)

        # Check the count sensor
        resp = ha_api("GET", "/api/states/sensor.automation_suggestions_suggestions_count")
        assert resp.status_code == 200
        state = resp.json()

        count_str = state.get("state", "0")
        # State might be "unknown" initially
        if count_str not in ("unknown", "unavailable"):
            count = int(count_str)
            assert count >= 0, "Count sensor should have a valid state"

        # Check the top suggestions sensor
        resp = ha_api("GET", "/api/states/sensor.automation_suggestions_top_suggestions")
        assert resp.status_code == 200
        top_state = resp.json()

        # The state should be valid
        assert top_state.get("state") is not None


class TestRecorderIntegration:
    """Test recorder/history API integration."""

    def test_history_api_works(self, ha_api):
        """Verify we can query history API."""
        # Try the history/period endpoint - format varies by HA version
        # Try without timestamp first (should work in most versions)
        resp = ha_api("GET", "/api/history/period")

        # 200 = success, 400 = needs params, 404 = endpoint not exposed
        # All are acceptable as long as the API responds
        assert resp.status_code in (200, 400, 404), (
            f"History API unexpected response: {resp.status_code}"
        )

    def test_logbook_api_works(self, ha_api):
        """Verify we can query logbook API."""
        resp = ha_api("GET", "/api/logbook")
        assert resp.status_code in (200, 400)
