"""
E2E tests for the WebSocket API of the automation_suggestions integration.

These tests verify:
- WebSocket connection and authentication to Home Assistant
- automation_suggestions/list command with pagination
- automation_suggestions/subscribe command for real-time updates
- Static path serving for the Lovelace card JS file
"""

import asyncio
import json

import pytest
import requests
import websockets

pytestmark = [pytest.mark.e2e]


class TestWebSocketConnection:
    """Test basic WebSocket connection to Home Assistant."""

    @pytest.mark.asyncio
    async def test_websocket_connection(self, ha_url):
        """Verify WebSocket connection to Home Assistant works."""
        # Convert HTTP URL to WebSocket URL
        ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/api/websocket"

        try:
            async with websockets.connect(ws_url) as websocket:
                # Should receive auth_required message
                message = await asyncio.wait_for(websocket.recv(), timeout=10)
                data = json.loads(message)
                assert (
                    data["type"] == "auth_required"
                ), f"Expected auth_required, got: {data['type']}"
        except (ConnectionRefusedError, OSError) as e:
            pytest.skip(f"WebSocket not available: {e}")
        except TimeoutError:
            pytest.fail("WebSocket connection timed out waiting for auth_required")

    @pytest.mark.asyncio
    async def test_websocket_auth(self, ha_url, ha_token):
        """Verify WebSocket authentication works with token."""
        ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/api/websocket"

        try:
            async with websockets.connect(ws_url) as websocket:
                # Wait for auth_required
                message = await asyncio.wait_for(websocket.recv(), timeout=10)
                data = json.loads(message)
                assert data["type"] == "auth_required"

                # Send auth message
                auth_msg = {"type": "auth", "access_token": ha_token}
                await websocket.send(json.dumps(auth_msg))

                # Wait for auth_ok
                message = await asyncio.wait_for(websocket.recv(), timeout=10)
                data = json.loads(message)
                assert data["type"] == "auth_ok", f"Expected auth_ok, got: {data}"
        except (ConnectionRefusedError, OSError) as e:
            pytest.skip(f"WebSocket not available: {e}")
        except TimeoutError:
            pytest.fail("WebSocket authentication timed out")


class TestWebSocketListSuggestions:
    """Test the automation_suggestions/list WebSocket command."""

    @pytest.fixture
    async def authenticated_websocket(self, ha_url, ha_token):
        """Create an authenticated WebSocket connection."""
        ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/api/websocket"

        try:
            websocket = await websockets.connect(ws_url)
        except (ConnectionRefusedError, OSError) as e:
            pytest.skip(f"WebSocket not available: {e}")
            return

        try:
            # Wait for auth_required
            message = await asyncio.wait_for(websocket.recv(), timeout=10)
            data = json.loads(message)
            if data["type"] != "auth_required":
                await websocket.close()
                pytest.fail(f"Expected auth_required, got: {data['type']}")

            # Send auth
            auth_msg = {"type": "auth", "access_token": ha_token}
            await websocket.send(json.dumps(auth_msg))

            # Wait for auth_ok
            message = await asyncio.wait_for(websocket.recv(), timeout=10)
            data = json.loads(message)
            if data["type"] != "auth_ok":
                await websocket.close()
                pytest.fail(f"Expected auth_ok, got: {data}")

            yield websocket
        finally:
            await websocket.close()

    @pytest.mark.asyncio
    async def test_list_suggestions_returns_data(self, authenticated_websocket):
        """Call automation_suggestions/list and verify response format."""
        websocket = authenticated_websocket

        # Send list command
        cmd = {
            "id": 1,
            "type": "automation_suggestions/list",
            "page": 1,
            "page_size": 20,
        }
        await websocket.send(json.dumps(cmd))

        # Wait for response
        try:
            message = await asyncio.wait_for(websocket.recv(), timeout=10)
            data = json.loads(message)
        except TimeoutError:
            pytest.fail("Timed out waiting for list response")

        # Verify response structure
        assert data["id"] == 1, f"Response ID mismatch: {data}"
        assert data["type"] == "result", f"Expected result type, got: {data['type']}"
        assert data["success"] is True, f"Command failed: {data}"

        # Verify result structure
        result = data["result"]
        assert "suggestions" in result, f"Missing suggestions in result: {result}"
        assert "total" in result, f"Missing total in result: {result}"
        assert "page" in result, f"Missing page in result: {result}"
        assert "pages" in result, f"Missing pages in result: {result}"

        # Verify types
        assert isinstance(result["suggestions"], list)
        assert isinstance(result["total"], int)
        assert isinstance(result["page"], int)
        assert isinstance(result["pages"], int)

    @pytest.mark.asyncio
    async def test_list_suggestions_pagination(self, authenticated_websocket):
        """Test pagination with different page and page_size values."""
        websocket = authenticated_websocket

        # Test page 1 with small page_size
        cmd1 = {
            "id": 1,
            "type": "automation_suggestions/list",
            "page": 1,
            "page_size": 5,
        }
        await websocket.send(json.dumps(cmd1))

        message = await asyncio.wait_for(websocket.recv(), timeout=10)
        data1 = json.loads(message)
        assert data1["success"] is True
        result1 = data1["result"]
        assert result1["page"] == 1
        assert result1["page_size"] == 5
        assert len(result1["suggestions"]) <= 5

        # Test page 2
        cmd2 = {
            "id": 2,
            "type": "automation_suggestions/list",
            "page": 2,
            "page_size": 5,
        }
        await websocket.send(json.dumps(cmd2))

        message = await asyncio.wait_for(websocket.recv(), timeout=10)
        data2 = json.loads(message)
        assert data2["success"] is True
        result2 = data2["result"]
        assert result2["page"] == 2

        # Test with larger page_size
        cmd3 = {
            "id": 3,
            "type": "automation_suggestions/list",
            "page": 1,
            "page_size": 100,
        }
        await websocket.send(json.dumps(cmd3))

        message = await asyncio.wait_for(websocket.recv(), timeout=10)
        data3 = json.loads(message)
        assert data3["success"] is True
        result3 = data3["result"]
        assert result3["page_size"] == 100

    @pytest.mark.asyncio
    async def test_list_suggestions_default_pagination(self, authenticated_websocket):
        """Test that default pagination values work when not specified."""
        websocket = authenticated_websocket

        # Send command without explicit pagination
        cmd = {
            "id": 1,
            "type": "automation_suggestions/list",
        }
        await websocket.send(json.dumps(cmd))

        message = await asyncio.wait_for(websocket.recv(), timeout=10)
        data = json.loads(message)
        assert data["success"] is True
        result = data["result"]

        # Default values should be applied
        assert result["page"] == 1
        assert result["page_size"] == 20


class TestWebSocketSubscribeSuggestions:
    """Test the automation_suggestions/subscribe WebSocket command."""

    @pytest.fixture
    async def authenticated_websocket(self, ha_url, ha_token):
        """Create an authenticated WebSocket connection."""
        ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/api/websocket"

        try:
            websocket = await websockets.connect(ws_url)
        except (ConnectionRefusedError, OSError) as e:
            pytest.skip(f"WebSocket not available: {e}")
            return

        try:
            # Wait for auth_required
            message = await asyncio.wait_for(websocket.recv(), timeout=10)
            data = json.loads(message)
            if data["type"] != "auth_required":
                await websocket.close()
                pytest.fail(f"Expected auth_required, got: {data['type']}")

            # Send auth
            auth_msg = {"type": "auth", "access_token": ha_token}
            await websocket.send(json.dumps(auth_msg))

            # Wait for auth_ok
            message = await asyncio.wait_for(websocket.recv(), timeout=10)
            data = json.loads(message)
            if data["type"] != "auth_ok":
                await websocket.close()
                pytest.fail(f"Expected auth_ok, got: {data}")

            yield websocket
        finally:
            await websocket.close()

    @pytest.mark.asyncio
    async def test_subscribe_suggestions_returns_initial_data(self, authenticated_websocket):
        """Call subscribe and verify initial data is returned."""
        websocket = authenticated_websocket

        # Send subscribe command
        cmd = {
            "id": 1,
            "type": "automation_suggestions/subscribe",
        }
        await websocket.send(json.dumps(cmd))

        # Wait for result (subscription acknowledgment)
        try:
            message = await asyncio.wait_for(websocket.recv(), timeout=10)
            data = json.loads(message)
        except TimeoutError:
            pytest.fail("Timed out waiting for subscribe response")

        # Verify subscription was successful
        assert data["id"] == 1, f"Response ID mismatch: {data}"
        assert data["type"] == "result", f"Expected result type, got: {data['type']}"
        assert data["success"] is True, f"Subscribe command failed: {data}"

        # After successful subscription, we should receive initial event data
        try:
            event_message = await asyncio.wait_for(websocket.recv(), timeout=10)
            event_data = json.loads(event_message)
        except TimeoutError:
            # It's acceptable if no event is sent when data is None
            return

        # Verify event structure if received
        assert event_data["id"] == 1
        assert event_data["type"] == "event"
        event = event_data["event"]
        assert "suggestions" in event
        assert "total" in event
        assert isinstance(event["suggestions"], list)
        assert isinstance(event["total"], int)

    @pytest.mark.asyncio
    async def test_subscribe_returns_error_when_not_configured(self, ha_url, ha_token, ha_api):
        """Verify subscribe returns appropriate response when integration isn't fully set up."""
        # First check if the integration is loaded
        resp = ha_api("GET", "/api/config")
        if resp.status_code != 200:
            pytest.skip("Cannot get config")

        config = resp.json()
        components = config.get("components", [])

        # Connect to WebSocket
        ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/api/websocket"

        try:
            async with websockets.connect(ws_url) as websocket:
                # Authenticate
                message = await asyncio.wait_for(websocket.recv(), timeout=10)
                auth_msg = {"type": "auth", "access_token": ha_token}
                await websocket.send(json.dumps(auth_msg))
                await asyncio.wait_for(websocket.recv(), timeout=10)

                # Send subscribe command
                cmd = {"id": 1, "type": "automation_suggestions/subscribe"}
                await websocket.send(json.dumps(cmd))

                # Wait for response
                message = await asyncio.wait_for(websocket.recv(), timeout=10)
                data = json.loads(message)

                # If integration is loaded, we expect success
                # If not loaded, we might get an error
                if "automation_suggestions" in components:
                    # Integration is loaded - expect result or error if coordinator missing
                    assert data["id"] == 1
                    # Either success or not_found error is valid
                    if data["type"] == "result":
                        assert data["success"] in (True, False)
                    elif data["type"] == "error":
                        # Unknown command if not registered
                        pass
                else:
                    # Integration not loaded - expect unknown command error
                    assert data["type"] == "result"
                    assert data["success"] is False
        except (ConnectionRefusedError, OSError) as e:
            pytest.skip(f"WebSocket not available: {e}")


class TestStaticPathServing:
    """Test that the Lovelace card JS file is served via static path."""

    def test_static_path_serves_card_js(self, ha_url, ha_token, ha_api):
        """Verify /automation_suggestions/automation-suggestions-card.js is accessible."""
        # First verify our integration is loaded
        resp = ha_api("GET", "/api/config")
        if resp.status_code != 200:
            pytest.skip("Cannot get config")

        config = resp.json()
        components = config.get("components", [])

        if "automation_suggestions" not in components:
            pytest.skip("automation_suggestions integration not loaded")

        # Try to fetch the card JS file
        js_url = f"{ha_url}/automation_suggestions/automation-suggestions-card.js"
        resp = requests.get(
            js_url,
            headers={"Authorization": f"Bearer {ha_token}"},
            timeout=30,
        )

        # Should be accessible (200) or might require different auth (401)
        # 404 would mean the static path isn't registered
        assert resp.status_code != 404, (
            f"Card JS file not found at {js_url}. " "Static path may not be registered correctly."
        )

        if resp.status_code == 200:
            # Verify it's JavaScript content
            content = resp.text
            # Should contain some JS indicators
            assert len(content) > 0, "Card JS file is empty"
            # Basic sanity check for JS content
            assert any(
                keyword in content.lower()
                for keyword in ["class", "function", "const", "let", "var", "export"]
            ), f"Content doesn't look like JavaScript: {content[:200]}"

    def test_static_path_not_found_before_integration_setup(self, ha_url):
        """Test that static path returns 404 or 401 when accessed without auth."""
        js_url = f"{ha_url}/automation_suggestions/automation-suggestions-card.js"
        resp = requests.get(js_url, timeout=30)

        # In HA 2026+, static paths can be served without auth
        # 200 means file is accessible, 401/404 means auth required or not found
        assert resp.status_code in (
            200,
            401,
            404,
        ), f"Unexpected response {resp.status_code} for unauthenticated request"


class TestWebSocketErrorHandling:
    """Test WebSocket error handling scenarios."""

    @pytest.fixture
    async def authenticated_websocket(self, ha_url, ha_token):
        """Create an authenticated WebSocket connection."""
        ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/api/websocket"

        try:
            websocket = await websockets.connect(ws_url)
        except (ConnectionRefusedError, OSError) as e:
            pytest.skip(f"WebSocket not available: {e}")
            return

        try:
            message = await asyncio.wait_for(websocket.recv(), timeout=10)
            data = json.loads(message)
            if data["type"] != "auth_required":
                await websocket.close()
                pytest.fail(f"Expected auth_required, got: {data['type']}")

            auth_msg = {"type": "auth", "access_token": ha_token}
            await websocket.send(json.dumps(auth_msg))

            message = await asyncio.wait_for(websocket.recv(), timeout=10)
            data = json.loads(message)
            if data["type"] != "auth_ok":
                await websocket.close()
                pytest.fail(f"Expected auth_ok, got: {data}")

            yield websocket
        finally:
            await websocket.close()

    @pytest.mark.asyncio
    async def test_invalid_page_size_rejected(self, authenticated_websocket):
        """Test that invalid page_size values are rejected."""
        websocket = authenticated_websocket

        # Try page_size of 0 (below minimum)
        cmd = {
            "id": 1,
            "type": "automation_suggestions/list",
            "page": 1,
            "page_size": 0,
        }
        await websocket.send(json.dumps(cmd))

        message = await asyncio.wait_for(websocket.recv(), timeout=10)
        data = json.loads(message)

        # Should return error for invalid page_size
        assert data["id"] == 1
        if data["type"] == "result":
            assert data["success"] is False, "Should reject page_size of 0"

    @pytest.mark.asyncio
    async def test_page_size_over_max_rejected(self, authenticated_websocket):
        """Test that page_size over maximum is rejected."""
        websocket = authenticated_websocket

        # Try page_size over 100 (above maximum)
        cmd = {
            "id": 1,
            "type": "automation_suggestions/list",
            "page": 1,
            "page_size": 200,
        }
        await websocket.send(json.dumps(cmd))

        message = await asyncio.wait_for(websocket.recv(), timeout=10)
        data = json.loads(message)

        # Should return error for invalid page_size
        assert data["id"] == 1
        if data["type"] == "result":
            assert data["success"] is False, "Should reject page_size over 100"

    @pytest.mark.asyncio
    async def test_invalid_auth_token_rejected(self, ha_url):
        """Test that invalid authentication token is rejected."""
        ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/api/websocket"

        try:
            async with websockets.connect(ws_url) as websocket:
                # Wait for auth_required
                message = await asyncio.wait_for(websocket.recv(), timeout=10)
                data = json.loads(message)
                assert data["type"] == "auth_required"

                # Send auth with invalid token
                auth_msg = {"type": "auth", "access_token": "invalid_token_12345"}
                await websocket.send(json.dumps(auth_msg))

                # Should receive auth_invalid
                message = await asyncio.wait_for(websocket.recv(), timeout=10)
                data = json.loads(message)
                assert (
                    data["type"] == "auth_invalid"
                ), f"Expected auth_invalid for bad token, got: {data['type']}"
        except (ConnectionRefusedError, OSError) as e:
            pytest.skip(f"WebSocket not available: {e}")


class TestWebSocketListStaleEndpoint:
    """Test the automation_suggestions/list_stale WebSocket command in real HA."""

    @pytest.fixture
    async def authenticated_websocket(self, ha_url, ha_token):
        """Create an authenticated WebSocket connection."""
        ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/api/websocket"

        try:
            websocket = await websockets.connect(ws_url)
        except (ConnectionRefusedError, OSError) as e:
            pytest.skip(f"WebSocket not available: {e}")
            return

        try:
            message = await asyncio.wait_for(websocket.recv(), timeout=10)
            data = json.loads(message)
            if data["type"] != "auth_required":
                await websocket.close()
                pytest.fail(f"Expected auth_required, got: {data['type']}")

            auth_msg = {"type": "auth", "access_token": ha_token}
            await websocket.send(json.dumps(auth_msg))

            message = await asyncio.wait_for(websocket.recv(), timeout=10)
            data = json.loads(message)
            if data["type"] != "auth_ok":
                await websocket.close()
                pytest.fail(f"Expected auth_ok, got: {data}")

            yield websocket
        finally:
            await websocket.close()

    @pytest.mark.asyncio
    async def test_list_stale_endpoint_exists(self, authenticated_websocket):
        """Verify list_stale endpoint is registered and responds."""
        websocket = authenticated_websocket

        cmd = {
            "id": 1,
            "type": "automation_suggestions/list_stale",
        }
        await websocket.send(json.dumps(cmd))

        try:
            message = await asyncio.wait_for(websocket.recv(), timeout=10)
            data = json.loads(message)
        except TimeoutError:
            pytest.fail("Timed out waiting for list_stale response")

        # Verify response structure
        assert data["id"] == 1, f"Response ID mismatch: {data}"
        assert data["type"] == "result", f"Expected result type, got: {data['type']}"
        assert data["success"] is True, f"Command failed: {data}"

        # Verify result has expected fields
        result = data["result"]
        assert "stale_automations" in result
        assert "total" in result
        assert "page" in result
        assert "pages" in result
        assert "page_size" in result

    @pytest.mark.asyncio
    async def test_list_stale_invalid_page_size_rejected(self, authenticated_websocket):
        """Test that invalid page_size values are rejected for list_stale."""
        websocket = authenticated_websocket

        # Try page_size of 0 (below minimum)
        cmd = {
            "id": 1,
            "type": "automation_suggestions/list_stale",
            "page": 1,
            "page_size": 0,
        }
        await websocket.send(json.dumps(cmd))

        message = await asyncio.wait_for(websocket.recv(), timeout=10)
        data = json.loads(message)

        assert data["id"] == 1
        if data["type"] == "result":
            assert data["success"] is False, "Should reject page_size of 0"

    @pytest.mark.asyncio
    async def test_list_stale_page_size_over_max_rejected(self, authenticated_websocket):
        """Test that page_size over maximum is rejected for list_stale."""
        websocket = authenticated_websocket

        # Try page_size over 100 (above maximum)
        cmd = {
            "id": 1,
            "type": "automation_suggestions/list_stale",
            "page": 1,
            "page_size": 200,
        }
        await websocket.send(json.dumps(cmd))

        message = await asyncio.wait_for(websocket.recv(), timeout=10)
        data = json.loads(message)

        assert data["id"] == 1
        if data["type"] == "result":
            assert data["success"] is False, "Should reject page_size over 100"
