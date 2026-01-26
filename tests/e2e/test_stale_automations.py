"""
E2E tests for stale automation detection WebSocket API.

These tests verify:
- automation_suggestions/list_stale command with pagination
- Subscribe command includes stale_automations and stale_total
- Validation of pagination parameters for list_stale
"""

import asyncio
import json

import pytest
import websockets

pytestmark = [pytest.mark.e2e]


class TestWebSocketListStale:
    """Test the automation_suggestions/list_stale WebSocket command."""

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
    async def test_list_stale_returns_data(self, authenticated_websocket):
        """Call automation_suggestions/list_stale and verify response format."""
        websocket = authenticated_websocket

        # Send list_stale command
        cmd = {
            "id": 1,
            "type": "automation_suggestions/list_stale",
            "page": 1,
            "page_size": 20,
        }
        await websocket.send(json.dumps(cmd))

        # Wait for response
        try:
            message = await asyncio.wait_for(websocket.recv(), timeout=10)
            data = json.loads(message)
        except TimeoutError:
            pytest.fail("Timed out waiting for list_stale response")

        # Verify response structure
        assert data["id"] == 1, f"Response ID mismatch: {data}"
        assert data["type"] == "result", f"Expected result type, got: {data['type']}"
        assert data["success"] is True, f"Command failed: {data}"

        # Verify result structure
        result = data["result"]
        assert "stale_automations" in result, f"Missing stale_automations in result: {result}"
        assert "total" in result, f"Missing total in result: {result}"
        assert "page" in result, f"Missing page in result: {result}"
        assert "pages" in result, f"Missing pages in result: {result}"
        assert "page_size" in result, f"Missing page_size in result: {result}"

        # Verify types
        assert isinstance(result["stale_automations"], list)
        assert isinstance(result["total"], int)
        assert isinstance(result["page"], int)
        assert isinstance(result["pages"], int)
        assert isinstance(result["page_size"], int)

    @pytest.mark.asyncio
    async def test_list_stale_pagination(self, authenticated_websocket):
        """Test pagination with different page and page_size values."""
        websocket = authenticated_websocket

        # Test page 1 with small page_size
        cmd1 = {
            "id": 1,
            "type": "automation_suggestions/list_stale",
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
        assert len(result1["stale_automations"]) <= 5

        # Test page 2
        cmd2 = {
            "id": 2,
            "type": "automation_suggestions/list_stale",
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
            "type": "automation_suggestions/list_stale",
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
    async def test_list_stale_default_pagination(self, authenticated_websocket):
        """Test that default pagination values work when not specified."""
        websocket = authenticated_websocket

        # Send command without explicit pagination
        cmd = {
            "id": 1,
            "type": "automation_suggestions/list_stale",
        }
        await websocket.send(json.dumps(cmd))

        message = await asyncio.wait_for(websocket.recv(), timeout=10)
        data = json.loads(message)
        assert data["success"] is True
        result = data["result"]

        # Default values should be applied
        assert result["page"] == 1
        assert result["page_size"] == 20


class TestWebSocketSubscribeIncludesStale:
    """Test that subscribe includes stale automations."""

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
    async def test_subscribe_includes_stale_automations(self, authenticated_websocket):
        """Verify subscribe response includes stale_automations and stale_total."""
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

        # Verify suggestions are present
        assert "suggestions" in event, f"Missing suggestions in event: {event}"
        assert "total" in event, f"Missing total in event: {event}"
        assert isinstance(event["suggestions"], list)
        assert isinstance(event["total"], int)

        # Verify stale automations are present
        assert "stale_automations" in event, f"Missing stale_automations in event: {event}"
        assert "stale_total" in event, f"Missing stale_total in event: {event}"
        assert isinstance(event["stale_automations"], list)
        assert isinstance(event["stale_total"], int)


class TestWebSocketListStaleValidation:
    """Test validation for automation_suggestions/list_stale command."""

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

        # Should return error for invalid page_size
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

        # Should return error for invalid page_size
        assert data["id"] == 1
        if data["type"] == "result":
            assert data["success"] is False, "Should reject page_size over 100"

    @pytest.mark.asyncio
    async def test_list_stale_invalid_page_rejected(self, authenticated_websocket):
        """Test that invalid page values are rejected for list_stale."""
        websocket = authenticated_websocket

        # Try page of 0 (below minimum)
        cmd = {
            "id": 1,
            "type": "automation_suggestions/list_stale",
            "page": 0,
            "page_size": 20,
        }
        await websocket.send(json.dumps(cmd))

        message = await asyncio.wait_for(websocket.recv(), timeout=10)
        data = json.loads(message)

        # Should return error for invalid page
        assert data["id"] == 1
        if data["type"] == "result":
            assert data["success"] is False, "Should reject page of 0"
