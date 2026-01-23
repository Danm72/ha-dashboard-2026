"""
E2E tests for recorder API compatibility.

These tests verify basic Home Assistant API connectivity.
More comprehensive tests are in test_analyzer.py.
"""

import pytest
import requests

pytestmark = [pytest.mark.e2e]


class TestHomeAssistantConnection:
    """Test basic HA connection."""

    def test_ha_api_accessible(self, ha_url):
        """Verify Home Assistant API is accessible without auth."""
        resp = requests.get(f"{ha_url}/api/", timeout=10)
        # 401 without auth means API is running
        assert resp.status_code in (200, 401)

    def test_ha_api_with_auth(self, ha_api):
        """Verify Home Assistant API works with auth token."""
        resp = ha_api("GET", "/api/")
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data
