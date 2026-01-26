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


class TestStaleAutomationDetectionLogic:
    """Test that stale detection correctly identifies stale vs non-stale automations."""

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

    @pytest.fixture
    def ha_session(self, ha_url, ha_token):
        """Create a requests session for REST API calls."""
        import requests

        session = requests.Session()
        session.headers["Authorization"] = f"Bearer {ha_token}"
        session.headers["Content-Type"] = "application/json"
        session.base_url = ha_url
        return session

    def _create_automation(self, session, automation_id, friendly_name):
        """Create a test automation via REST API.

        Args:
            session: Configured requests session
            automation_id: The ID part (after 'automation.')
            friendly_name: Human-readable name

        Returns:
            Response from the API
        """
        # Create automation configuration
        automation_config = {
            "alias": friendly_name,
            "trigger": [
                {
                    "platform": "time",
                    "at": "00:00:00",
                }
            ],
            "action": [
                {
                    "service": "logger.log",
                    "data": {"message": f"Test automation {automation_id} triggered"},
                }
            ],
        }

        url = f"{session.base_url}/api/config/automation/config/{automation_id}"
        return session.post(url, json=automation_config, timeout=30)

    def _delete_automation(self, session, automation_id):
        """Delete a test automation via REST API."""
        url = f"{session.base_url}/api/config/automation/config/{automation_id}"
        return session.delete(url, timeout=30)

    def _trigger_automation(self, session, entity_id):
        """Trigger an automation to update its last_triggered timestamp.

        Args:
            session: Configured requests session
            entity_id: Full entity ID (e.g., 'automation.test_triggered')

        Returns:
            Response from the API
        """
        url = f"{session.base_url}/api/services/automation/trigger"
        return session.post(url, json={"entity_id": entity_id}, timeout=30)

    def _trigger_analysis(self, session):
        """Trigger the analyze_now service to refresh stale automation detection."""
        url = f"{session.base_url}/api/services/automation_suggestions/analyze_now"
        return session.post(url, json={}, timeout=30)

    def _get_entity_state(self, session, entity_id):
        """Get the state of an entity via REST API."""
        url = f"{session.base_url}/api/states/{entity_id}"
        return session.get(url, timeout=30)

    def _list_automation_entities(self, session):
        """List all automation entities from the state machine."""
        url = f"{session.base_url}/api/states"
        resp = session.get(url, timeout=30)
        if resp.status_code == 200:
            all_states = resp.json()
            return [state["entity_id"] for state in all_states if state["entity_id"].startswith("automation.")]
        return []

    def _reload_automations(self, session):
        """Reload automation domain to pick up new automations."""
        resp = session.post(
            f"{session.base_url}/api/services/automation/reload",
            json={},
        )
        return resp

    async def _wait_for_entity(self, session, entity_id, max_retries=20, delay=0.5):
        """Wait for an entity to exist in the state machine.

        Args:
            session: Configured requests session
            entity_id: Full entity ID to check
            max_retries: Maximum number of retries (default 20 = 10 seconds total)
            delay: Delay between retries in seconds

        Returns:
            True if entity exists, False otherwise
        """
        import logging

        logger = logging.getLogger(__name__)

        for attempt in range(max_retries):
            # On first attempt, list all automation entities for debugging
            if attempt == 0:
                all_automations = self._list_automation_entities(session)
                logger.debug(f"All automation entities in state machine: {all_automations}")

            resp = self._get_entity_state(session, entity_id)
            logger.debug(
                f"Entity check attempt {attempt + 1}/{max_retries} for {entity_id}: "
                f"status={resp.status_code}"
            )
            if resp.status_code == 200:
                logger.debug(f"Entity {entity_id} found: {resp.json()}")
                return True
            await asyncio.sleep(delay)
        return False

    async def _subscribe_and_wait_for_update(self, websocket, msg_id, trigger_func, timeout=30):
        """Subscribe to updates and wait for an update event after triggering an action.

        This method:
        1. Subscribes to automation_suggestions/subscribe
        2. Waits for the subscription result
        3. Waits for the initial event
        4. Calls the trigger function (e.g., analyze_now)
        5. Waits for the next event (from coordinator update)

        Args:
            websocket: Authenticated WebSocket connection
            msg_id: Message ID to use for subscription
            trigger_func: Callable that triggers the action (e.g., analyze_now)
            timeout: Total timeout in seconds

        Returns:
            The event data from the update event containing stale_automations
        """
        import logging

        logger = logging.getLogger(__name__)

        # Step 1: Subscribe
        subscribe_cmd = {
            "id": msg_id,
            "type": "automation_suggestions/subscribe",
        }
        await websocket.send(json.dumps(subscribe_cmd))
        logger.debug(f"Sent subscribe command with id={msg_id}")

        # Step 2: Wait for subscription result
        message = await asyncio.wait_for(websocket.recv(), timeout=timeout)
        data = json.loads(message)
        logger.debug(
            f"Received message after subscribe: type={data.get('type')}, id={data.get('id')}"
        )

        assert data["id"] == msg_id, f"Expected id={msg_id}, got {data['id']}"
        assert data["type"] == "result", f"Expected result type, got: {data['type']}"
        assert data["success"] is True, f"Subscribe failed: {data}"

        # Step 3: Wait for initial event
        message = await asyncio.wait_for(websocket.recv(), timeout=timeout)
        initial_event = json.loads(message)
        logger.debug(
            f"Received initial event: type={initial_event.get('type')}, "
            f"stale_total={initial_event.get('event', {}).get('stale_total')}"
        )

        assert initial_event["id"] == msg_id
        assert initial_event["type"] == "event"
        initial_stale_ids = [
            s["automation_id"] for s in initial_event["event"].get("stale_automations", [])
        ]
        logger.debug(f"Initial stale automation IDs: {initial_stale_ids}")

        # Step 4: Trigger the action (e.g., analyze_now)
        logger.debug("Calling trigger function...")
        trigger_func()

        # Step 5: Wait for update event (skip events for other subscription IDs)
        logger.debug("Waiting for update event from coordinator...")
        while True:
            message = await asyncio.wait_for(websocket.recv(), timeout=timeout)
            update_event = json.loads(message)
            logger.debug(
                f"Received event: id={update_event.get('id')}, type={update_event.get('type')}, "
                f"stale_total={update_event.get('event', {}).get('stale_total')}"
            )

            # Skip events from other subscriptions
            if update_event.get("id") != msg_id:
                logger.debug(f"Skipping event for id={update_event.get('id')}, waiting for id={msg_id}")
                continue

            assert update_event["type"] == "event"
            break

        updated_stale_ids = [
            s["automation_id"] for s in update_event["event"].get("stale_automations", [])
        ]
        logger.debug(f"Updated stale automation IDs: {updated_stale_ids}")

        return update_event["event"]

    @pytest.mark.asyncio
    async def test_triggered_automation_not_in_stale_list(
        self, ha_url, ha_token, ha_session, authenticated_websocket
    ):
        """Test that a recently triggered automation is NOT in the stale list.

        This test:
        1. Creates two test automations
        2. Verifies the automations exist in the state machine
        3. Triggers one of them (giving it a recent last_triggered)
        4. Subscribes to updates and triggers analysis
        5. Waits for the update event (not time-based)
        6. Verifies the triggered automation is NOT stale
        7. Verifies the non-triggered automation IS stale (never triggered = 999 days)
        """
        import logging
        import time

        logger = logging.getLogger(__name__)

        websocket = authenticated_websocket
        session = ha_session

        # Generate unique IDs for this test run
        test_id = int(time.time())
        triggered_id = f"e2e_test_triggered_{test_id}"
        not_triggered_id = f"e2e_test_not_triggered_{test_id}"
        triggered_entity = f"automation.{triggered_id}"
        not_triggered_entity = f"automation.{not_triggered_id}"

        try:
            # Step 1: Create two test automations
            logger.debug(f"Creating automation: {triggered_id}")
            resp1 = self._create_automation(session, triggered_id, f"E2E Test Triggered {test_id}")
            logger.debug(
                f"Create triggered automation response: status={resp1.status_code}, body={resp1.text}"
            )
            assert resp1.status_code in (
                200,
                201,
            ), f"Failed to create triggered automation: {resp1.text}"

            logger.debug(f"Creating automation: {not_triggered_id}")
            resp2 = self._create_automation(
                session, not_triggered_id, f"E2E Test Not Triggered {test_id}"
            )
            logger.debug(
                f"Create not-triggered automation response: status={resp2.status_code}, body={resp2.text}"
            )
            assert resp2.status_code in (
                200,
                201,
            ), f"Failed to create non-triggered automation: {resp2.text}"

            # Reload automations to register them in the state machine
            logger.debug("Reloading automations...")
            reload_resp = self._reload_automations(session)
            logger.debug(f"Reload response: status={reload_resp.status_code}")
            assert reload_resp.status_code in (
                200,
                201,
            ), f"Failed to reload automations: {reload_resp.text}"

            # Step 2: Verify automations exist in the state machine
            logger.debug(f"Waiting for {triggered_entity} to exist...")
            triggered_exists = await self._wait_for_entity(session, triggered_entity)
            assert (
                triggered_exists
            ), f"Automation {triggered_entity} was not created in state machine"

            logger.debug(f"Waiting for {not_triggered_entity} to exist...")
            not_triggered_exists = await self._wait_for_entity(session, not_triggered_entity)
            assert (
                not_triggered_exists
            ), f"Automation {not_triggered_entity} was not created in state machine"

            # Step 3: Trigger one automation to give it a recent last_triggered
            logger.debug(f"Triggering automation: {triggered_entity}")
            trigger_resp = self._trigger_automation(session, triggered_entity)
            logger.debug(
                f"Trigger response: status={trigger_resp.status_code}, body={trigger_resp.text}"
            )
            assert trigger_resp.status_code in (
                200,
                201,
            ), f"Failed to trigger automation: {trigger_resp.text}"

            # Brief wait for trigger to be processed
            await asyncio.sleep(2)

            # DEBUG: Check the automation state after triggering
            state_resp = self._get_entity_state(session, triggered_entity)
            if state_resp.status_code == 200:
                state_data = state_resp.json()
                attrs = state_data.get("attributes", {})
                last_triggered = attrs.get("last_triggered")
                logger.debug(
                    f"DEBUG: After trigger - {triggered_entity} last_triggered={last_triggered}, "
                    f"state={state_data.get('state')}, all_attrs={attrs}"
                )
            else:
                logger.debug(f"DEBUG: Failed to get state of {triggered_entity}: {state_resp.status_code}")

            # Step 4 & 5: Subscribe to updates and wait for analysis to complete
            logger.debug("Subscribing and triggering analysis...")

            # DEBUG: Verify state is still correct right before analysis
            state_check = self._get_entity_state(session, triggered_entity)
            if state_check.status_code == 200:
                state_data = state_check.json()
                lt = state_data.get("attributes", {}).get("last_triggered")
                logger.debug(f"DEBUG: Pre-analysis state check - {triggered_entity} last_triggered={lt}")

            def trigger_analysis():
                analysis_resp = self._trigger_analysis(session)
                logger.debug(f"Analysis trigger response: status={analysis_resp.status_code}")
                assert analysis_resp.status_code in (
                    200,
                    201,
                ), f"Failed to trigger analysis: {analysis_resp.text}"

            event_data = await self._subscribe_and_wait_for_update(
                websocket, msg_id=1, trigger_func=trigger_analysis, timeout=30
            )

            # Step 6 & 7: Verify results from the update event
            stale_automations = event_data.get("stale_automations", [])
            stale_ids = [s["automation_id"] for s in stale_automations]
            logger.debug(f"Final stale automation IDs: {stale_ids}")

            # DEBUG: Log full stale automation data to understand why triggered is being included
            for stale_auto in stale_automations:
                logger.debug(
                    f"DEBUG Stale: {stale_auto['automation_id']} - "
                    f"days_since_triggered={stale_auto.get('days_since_triggered')}, "
                    f"last_triggered={stale_auto.get('last_triggered')}"
                )

            # The triggered automation should NOT be in the stale list
            # (it was just triggered, so last_triggered is recent)
            assert triggered_entity not in stale_ids, (
                f"Recently triggered automation {triggered_entity} should NOT be stale. "
                f"Stale list contains: {stale_ids}"
            )

            # The non-triggered automation SHOULD be in the stale list
            # (never triggered = 999 days since trigger > 30 day threshold)
            assert not_triggered_entity in stale_ids, (
                f"Never-triggered automation {not_triggered_entity} should be stale. "
                f"Stale list contains: {stale_ids}"
            )

            # Verify the stale automation has correct properties
            not_triggered_stale = next(
                (s for s in stale_automations if s["automation_id"] == not_triggered_entity),
                None,
            )
            assert not_triggered_stale is not None
            # Never triggered should have 999 days or very high value
            assert not_triggered_stale["days_since_triggered"] >= 30, (
                f"Never-triggered automation should have days_since_triggered >= 30, "
                f"got {not_triggered_stale['days_since_triggered']}"
            )

        finally:
            # Cleanup: Delete test automations
            logger.debug(f"Cleaning up: deleting {triggered_id} and {not_triggered_id}")
            self._delete_automation(session, triggered_id)
            self._delete_automation(session, not_triggered_id)
            # Reload automations to remove deleted entities from state machine
            self._reload_automations(session)

    @pytest.mark.asyncio
    async def test_stale_detection_counts_match(
        self, ha_url, ha_token, ha_session, authenticated_websocket
    ):
        """Test that stale automation total count is accurate after triggering.

        This test verifies that the total count in the stale list response
        accurately reflects the number of stale automations.
        """
        import logging
        import time

        logger = logging.getLogger(__name__)

        websocket = authenticated_websocket
        session = ha_session

        # DEBUG: Log ALL automation entities at start of test
        all_automations = self._list_automation_entities(session)
        logger.info(f"DEBUG: All automation entities at test start: {all_automations}")

        # Subscribe and wait for initial analysis to establish baseline
        # (This ensures we wait for the coordinator update, not just fire-and-forget)
        logger.debug("Subscribing and triggering initial analysis for baseline...")

        def trigger_initial_analysis():
            analysis_resp = self._trigger_analysis(session)
            logger.debug(f"Initial analysis trigger response: status={analysis_resp.status_code}")
            assert analysis_resp.status_code in (
                200,
                201,
            ), f"Failed to trigger initial analysis: {analysis_resp.text}"

        baseline_event = await self._subscribe_and_wait_for_update(
            websocket, msg_id=1, trigger_func=trigger_initial_analysis, timeout=30
        )

        initial_total = baseline_event.get("stale_total", 0)
        initial_stale_ids = [s["automation_id"] for s in baseline_event.get("stale_automations", [])]
        logger.info(f"Initial stale count: {initial_total}, IDs: {initial_stale_ids}")

        # DEBUG: Log details of each stale automation
        for stale in baseline_event.get("stale_automations", []):
            logger.info(f"DEBUG Baseline stale: {stale['automation_id']} - days_since={stale.get('days_since_triggered')}")

        # Create a new automation (never triggered = stale)
        test_id = int(time.time())
        test_automation_id = f"e2e_test_count_{test_id}"
        test_entity = f"automation.{test_automation_id}"

        try:
            logger.debug(f"Creating automation: {test_automation_id}")
            resp = self._create_automation(session, test_automation_id, f"E2E Test Count {test_id}")
            logger.debug(f"Create automation response: status={resp.status_code}, body={resp.text}")
            assert resp.status_code in (200, 201), f"Failed to create automation: {resp.text}"

            # Reload automations to register them in the state machine
            logger.debug("Reloading automations...")
            reload_resp = self._reload_automations(session)
            logger.debug(f"Reload response: status={reload_resp.status_code}")
            assert reload_resp.status_code in (
                200,
                201,
            ), f"Failed to reload automations: {reload_resp.text}"

            # Wait for entity to exist in state machine
            logger.debug(f"Waiting for {test_entity} to exist...")
            entity_exists = await self._wait_for_entity(session, test_entity)
            assert entity_exists, f"Automation {test_entity} was not created in state machine"

            # Subscribe and trigger analysis, wait for update event
            logger.debug("Subscribing and triggering analysis...")

            def trigger_analysis():
                analysis_resp = self._trigger_analysis(session)
                logger.debug(f"Analysis trigger response: status={analysis_resp.status_code}")
                assert analysis_resp.status_code in (
                    200,
                    201,
                ), f"Failed to trigger analysis: {analysis_resp.text}"

            event_data = await self._subscribe_and_wait_for_update(
                websocket, msg_id=2, trigger_func=trigger_analysis, timeout=30
            )

            # Get results from the update event
            new_stale_automations = event_data.get("stale_automations", [])
            new_total = event_data.get("stale_total", 0)
            new_stale_ids = [s["automation_id"] for s in new_stale_automations]
            logger.info(f"New stale count: {new_total}, IDs: {new_stale_ids}")

            # The new automation should be in the stale list
            assert test_entity in new_stale_ids, (
                f"New automation {test_entity} should be in stale list. "
                f"Stale list: {new_stale_ids}"
            )

            # Total should have increased by 1
            assert new_total == initial_total + 1, (
                f"Total should increase from {initial_total} to {initial_total + 1}, "
                f"but got {new_total}"
            )

            # List length should match total
            assert len(new_stale_automations) == new_total, (
                f"Stale list length {len(new_stale_automations)} " f"should match total {new_total}"
            )

        finally:
            # Cleanup
            logger.debug(f"Cleaning up: deleting {test_automation_id}")
            self._delete_automation(session, test_automation_id)
            # Reload automations to remove deleted entities from state machine
            self._reload_automations(session)
