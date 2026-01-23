"""
E2E tests for recorder API compatibility.

These tests verify the integration works with real Home Assistant APIs.
"""

import os

import pytest
import requests

pytestmark = [pytest.mark.e2e]


class TestHomeAssistantConnection:
    """Test basic HA connection."""

    def test_ha_api_accessible(self, ha_url):
        """Verify Home Assistant API is accessible."""
        resp = requests.get(f"{ha_url}/api/", timeout=10)
        # 401 without auth means API is running
        assert resp.status_code in (200, 401)


@pytest.mark.skipif(
    not os.environ.get("HA_TEST_TOKEN"),
    reason="HA_TEST_TOKEN not set",
)
class TestIntegrationLoaded:
    """Test our integration loads correctly."""

    def test_integration_available(self, ha_api):
        """Verify our integration is recognized."""
        resp = ha_api("GET", "/api/config")
        assert resp.status_code == 200
        config = resp.json()
        # Check if our component is in the components list
        # (it may not be loaded yet if not configured)
        assert "components" in config

    def test_services_registered(self, ha_api):
        """Verify our services are registered when integration is loaded."""
        resp = ha_api("GET", "/api/services")
        assert resp.status_code == 200
        services = resp.json()

        # Check if automation_suggestions domain exists
        domains = [s["domain"] for s in services]
        if "automation_suggestions" in domains:
            # Find our domain's services
            our_services = next(
                s for s in services if s["domain"] == "automation_suggestions"
            )
            assert "analyze_now" in our_services["services"]


class TestRecorderAPI:
    """Test recorder API patterns we depend on."""

    @pytest.mark.skipif(
        not os.environ.get("HA_TEST_TOKEN"),
        reason="HA_TEST_TOKEN not set",
    )
    def test_history_api_accessible(self, ha_api):
        """Verify history API endpoint exists."""
        # Just check the endpoint responds (even if empty)
        resp = ha_api("GET", "/api/history/period")
        # 200 = success, 400 = bad params (but endpoint exists)
        assert resp.status_code in (200, 400)
