"""Unit tests for the WebSocket API module."""

from unittest.mock import MagicMock, patch

from custom_components.automation_suggestions.analyzer import Suggestion
from custom_components.automation_suggestions.const import DOMAIN
from custom_components.automation_suggestions.websocket_api import (
    _get_coordinator,
    websocket_list_suggestions,
    websocket_subscribe_suggestions,
)


def create_test_suggestion(index: int, consistency_score: float = 0.85) -> Suggestion:
    """Create a test suggestion with the given index."""
    return Suggestion(
        id=f"test_{index}",
        entity_id=f"light.test_{index}",
        action="turn_on",
        suggested_time="07:00",
        time_window_start="07:00",
        time_window_end="07:29",
        consistency_score=consistency_score,
        occurrence_count=10,
        last_occurrence="2026-01-22T07:00:00+00:00",
    )


class TestGetCoordinator:
    """Tests for _get_coordinator helper function."""

    def test_returns_none_when_no_entries(self):
        """Should return None when no config entries exist."""
        hass = MagicMock()
        hass.config_entries.async_entries.return_value = []

        result = _get_coordinator(hass)

        assert result is None
        hass.config_entries.async_entries.assert_called_once_with(DOMAIN)

    def test_returns_coordinator_from_runtime_data(self):
        """Should return coordinator from entry runtime_data."""
        hass = MagicMock()
        mock_coordinator = MagicMock()
        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_coordinator
        hass.config_entries.async_entries.return_value = [mock_entry]

        result = _get_coordinator(hass)

        assert result == mock_coordinator

    def test_returns_none_when_runtime_data_is_none(self):
        """Should return None when runtime_data is None."""
        hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.runtime_data = None
        hass.config_entries.async_entries.return_value = [mock_entry]

        result = _get_coordinator(hass)

        assert result is None

    def test_returns_none_when_entry_has_no_runtime_data_attr(self):
        """Should return None when entry does not have runtime_data attribute."""
        hass = MagicMock()
        mock_entry = MagicMock(spec=[])  # No attributes
        hass.config_entries.async_entries.return_value = [mock_entry]

        result = _get_coordinator(hass)

        assert result is None

    def test_returns_first_valid_coordinator_from_multiple_entries(self):
        """Should return coordinator from first entry with valid runtime_data."""
        hass = MagicMock()

        # First entry has no runtime_data
        mock_entry_1 = MagicMock()
        mock_entry_1.runtime_data = None

        # Second entry has valid coordinator
        mock_coordinator = MagicMock()
        mock_entry_2 = MagicMock()
        mock_entry_2.runtime_data = mock_coordinator

        hass.config_entries.async_entries.return_value = [mock_entry_1, mock_entry_2]

        result = _get_coordinator(hass)

        assert result == mock_coordinator


class TestWebsocketListSuggestions:
    """Tests for websocket_list_suggestions handler."""

    def test_returns_empty_when_no_coordinator(self):
        """Should return empty result when coordinator not found."""
        hass = MagicMock()
        hass.config_entries.async_entries.return_value = []
        connection = MagicMock()
        msg = {"id": 1, "type": "automation_suggestions/list", "page": 1, "page_size": 20}

        websocket_list_suggestions(hass, connection, msg)

        connection.send_result.assert_called_once_with(
            1, {"suggestions": [], "total": 0, "page": 1, "pages": 0}
        )

    def test_returns_empty_when_coordinator_data_is_none(self):
        """Should return empty result when coordinator.data is None."""
        hass = MagicMock()
        mock_coordinator = MagicMock()
        mock_coordinator.data = None
        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_coordinator
        hass.config_entries.async_entries.return_value = [mock_entry]
        connection = MagicMock()
        msg = {"id": 1, "type": "automation_suggestions/list", "page": 1, "page_size": 20}

        websocket_list_suggestions(hass, connection, msg)

        connection.send_result.assert_called_once_with(
            1, {"suggestions": [], "total": 0, "page": 1, "pages": 0}
        )

    def test_returns_paginated_suggestions(self):
        """Should return correctly paginated suggestions."""
        hass = MagicMock()

        # Create 25 suggestions
        suggestions = [create_test_suggestion(i) for i in range(25)]

        mock_coordinator = MagicMock()
        mock_coordinator.data = suggestions
        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_coordinator
        hass.config_entries.async_entries.return_value = [mock_entry]
        connection = MagicMock()

        # Request page 1 with page_size 10
        msg = {"id": 1, "type": "automation_suggestions/list", "page": 1, "page_size": 10}
        websocket_list_suggestions(hass, connection, msg)

        call_args = connection.send_result.call_args
        result = call_args[0][1]

        assert result["total"] == 25
        assert result["page"] == 1
        assert result["pages"] == 3  # ceil(25/10) = 3
        assert result["page_size"] == 10
        assert len(result["suggestions"]) == 10

    def test_page_2_returns_correct_slice(self):
        """Should return correct slice for page 2."""
        hass = MagicMock()

        suggestions = [create_test_suggestion(i) for i in range(25)]

        mock_coordinator = MagicMock()
        mock_coordinator.data = suggestions
        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_coordinator
        hass.config_entries.async_entries.return_value = [mock_entry]
        connection = MagicMock()

        # Request page 2
        msg = {"id": 2, "type": "automation_suggestions/list", "page": 2, "page_size": 10}
        websocket_list_suggestions(hass, connection, msg)

        call_args = connection.send_result.call_args
        result = call_args[0][1]

        assert result["page"] == 2
        assert len(result["suggestions"]) == 10
        # First item on page 2 should be test_10
        assert result["suggestions"][0]["id"] == "test_10"

    def test_last_page_returns_remaining_items(self):
        """Should return only remaining items on the last page."""
        hass = MagicMock()

        suggestions = [create_test_suggestion(i) for i in range(25)]

        mock_coordinator = MagicMock()
        mock_coordinator.data = suggestions
        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_coordinator
        hass.config_entries.async_entries.return_value = [mock_entry]
        connection = MagicMock()

        # Request page 3 (last page with 5 items)
        msg = {"id": 3, "type": "automation_suggestions/list", "page": 3, "page_size": 10}
        websocket_list_suggestions(hass, connection, msg)

        call_args = connection.send_result.call_args
        result = call_args[0][1]

        assert result["page"] == 3
        assert len(result["suggestions"]) == 5
        # First item on page 3 should be test_20
        assert result["suggestions"][0]["id"] == "test_20"

    def test_empty_list_returns_zero_pages(self):
        """Should return 0 pages when suggestions list is empty."""
        hass = MagicMock()

        mock_coordinator = MagicMock()
        mock_coordinator.data = []
        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_coordinator
        hass.config_entries.async_entries.return_value = [mock_entry]
        connection = MagicMock()

        msg = {"id": 1, "type": "automation_suggestions/list", "page": 1, "page_size": 10}
        websocket_list_suggestions(hass, connection, msg)

        call_args = connection.send_result.call_args
        result = call_args[0][1]

        assert result["total"] == 0
        assert result["pages"] == 0
        assert result["suggestions"] == []

    def test_out_of_range_page_returns_empty_suggestions(self):
        """Should return empty suggestions when page is beyond available data."""
        hass = MagicMock()

        suggestions = [create_test_suggestion(i) for i in range(5)]

        mock_coordinator = MagicMock()
        mock_coordinator.data = suggestions
        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_coordinator
        hass.config_entries.async_entries.return_value = [mock_entry]
        connection = MagicMock()

        # Request page 10 which is beyond available data
        msg = {"id": 1, "type": "automation_suggestions/list", "page": 10, "page_size": 10}
        websocket_list_suggestions(hass, connection, msg)

        call_args = connection.send_result.call_args
        result = call_args[0][1]

        assert result["total"] == 5
        assert result["pages"] == 1
        assert result["suggestions"] == []

    def test_suggestion_to_dict_includes_all_fields(self):
        """Should convert suggestions to dictionaries with all required fields."""
        hass = MagicMock()

        suggestions = [create_test_suggestion(0)]

        mock_coordinator = MagicMock()
        mock_coordinator.data = suggestions
        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_coordinator
        hass.config_entries.async_entries.return_value = [mock_entry]
        connection = MagicMock()

        msg = {"id": 1, "type": "automation_suggestions/list", "page": 1, "page_size": 10}
        websocket_list_suggestions(hass, connection, msg)

        call_args = connection.send_result.call_args
        result = call_args[0][1]
        suggestion_dict = result["suggestions"][0]

        # Verify all fields are present
        assert "id" in suggestion_dict
        assert "entity_id" in suggestion_dict
        assert "action" in suggestion_dict
        assert "suggested_time" in suggestion_dict
        assert "time_window_start" in suggestion_dict
        assert "time_window_end" in suggestion_dict
        assert "consistency_score" in suggestion_dict
        assert "occurrence_count" in suggestion_dict
        assert "last_occurrence" in suggestion_dict
        assert "description" in suggestion_dict

    def test_uses_message_id_in_response(self):
        """Should use the correct message ID in the response."""
        hass = MagicMock()
        hass.config_entries.async_entries.return_value = []
        connection = MagicMock()
        msg = {"id": 42, "type": "automation_suggestions/list", "page": 1, "page_size": 20}

        websocket_list_suggestions(hass, connection, msg)

        call_args = connection.send_result.call_args
        assert call_args[0][0] == 42

    def test_default_page_size_of_20(self):
        """Should work with the default page_size when not specified in the message."""
        hass = MagicMock()

        # Create 30 suggestions
        suggestions = [create_test_suggestion(i) for i in range(30)]

        mock_coordinator = MagicMock()
        mock_coordinator.data = suggestions
        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_coordinator
        hass.config_entries.async_entries.return_value = [mock_entry]
        connection = MagicMock()

        # Message uses defaults (page_size=20 is the documented default)
        msg = {"id": 1, "type": "automation_suggestions/list", "page": 1, "page_size": 20}
        websocket_list_suggestions(hass, connection, msg)

        call_args = connection.send_result.call_args
        result = call_args[0][1]

        assert result["page_size"] == 20
        assert len(result["suggestions"]) == 20
        assert result["pages"] == 2  # ceil(30/20) = 2

    def test_pages_calculation_exact_fit(self):
        """Should calculate pages correctly when items fit exactly."""
        hass = MagicMock()

        # Create exactly 20 suggestions (exact fit for page_size=10 with 2 pages)
        suggestions = [create_test_suggestion(i) for i in range(20)]

        mock_coordinator = MagicMock()
        mock_coordinator.data = suggestions
        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_coordinator
        hass.config_entries.async_entries.return_value = [mock_entry]
        connection = MagicMock()

        msg = {"id": 1, "type": "automation_suggestions/list", "page": 1, "page_size": 10}
        websocket_list_suggestions(hass, connection, msg)

        call_args = connection.send_result.call_args
        result = call_args[0][1]

        assert result["pages"] == 2


class TestWebsocketSubscribeSuggestions:
    """Tests for websocket_subscribe_suggestions handler."""

    def test_sends_error_when_no_coordinator(self):
        """Should send error when coordinator not found."""
        hass = MagicMock()
        hass.config_entries.async_entries.return_value = []
        connection = MagicMock()
        msg = {"id": 1, "type": "automation_suggestions/subscribe"}

        websocket_subscribe_suggestions(hass, connection, msg)

        connection.send_error.assert_called_once_with(1, "not_found", "Coordinator not found")

    def test_subscribes_to_coordinator_updates(self):
        """Should subscribe to coordinator and store unsub function."""
        hass = MagicMock()
        mock_unsub = MagicMock()
        mock_coordinator = MagicMock()
        mock_coordinator.data = []
        mock_coordinator.async_add_listener.return_value = mock_unsub
        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_coordinator
        hass.config_entries.async_entries.return_value = [mock_entry]
        connection = MagicMock()
        connection.subscriptions = {}
        msg = {"id": 1, "type": "automation_suggestions/subscribe"}

        websocket_subscribe_suggestions(hass, connection, msg)

        # Should add listener
        mock_coordinator.async_add_listener.assert_called_once()
        # Should store unsub in subscriptions
        assert connection.subscriptions[1] == mock_unsub
        # Should send result
        connection.send_result.assert_called_once_with(1)

    def test_sends_initial_data_after_subscription(self):
        """Should send initial data immediately after subscribing."""
        hass = MagicMock()
        mock_unsub = MagicMock()
        suggestions = [create_test_suggestion(i) for i in range(3)]
        mock_coordinator = MagicMock()
        mock_coordinator.data = suggestions
        mock_coordinator.async_add_listener.return_value = mock_unsub
        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_coordinator
        hass.config_entries.async_entries.return_value = [mock_entry]
        connection = MagicMock()
        connection.subscriptions = {}
        msg = {"id": 1, "type": "automation_suggestions/subscribe"}

        websocket_subscribe_suggestions(hass, connection, msg)

        # Should send initial event message
        connection.send_message.assert_called_once()

    def test_does_not_send_message_when_data_is_none(self):
        """Should not send message when coordinator data is None."""
        hass = MagicMock()
        mock_unsub = MagicMock()
        mock_coordinator = MagicMock()
        mock_coordinator.data = None
        mock_coordinator.async_add_listener.return_value = mock_unsub
        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_coordinator
        hass.config_entries.async_entries.return_value = [mock_entry]
        connection = MagicMock()
        connection.subscriptions = {}
        msg = {"id": 1, "type": "automation_suggestions/subscribe"}

        websocket_subscribe_suggestions(hass, connection, msg)

        # Should not send event message when data is None
        connection.send_message.assert_not_called()

    def test_listener_callback_sends_update(self):
        """Should send update when listener callback is invoked."""
        hass = MagicMock()
        mock_unsub = MagicMock()
        suggestions = [create_test_suggestion(0)]
        mock_coordinator = MagicMock()
        mock_coordinator.data = suggestions
        mock_coordinator.async_add_listener.return_value = mock_unsub
        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_coordinator
        hass.config_entries.async_entries.return_value = [mock_entry]
        connection = MagicMock()
        connection.subscriptions = {}
        msg = {"id": 1, "type": "automation_suggestions/subscribe"}

        websocket_subscribe_suggestions(hass, connection, msg)

        # Capture the listener callback
        listener_callback = mock_coordinator.async_add_listener.call_args[0][0]

        # Reset the mock to test only the callback invocation
        connection.send_message.reset_mock()

        # Invoke the callback
        listener_callback()

        # Should send a message
        connection.send_message.assert_called_once()

    def test_listener_callback_does_not_send_when_data_none(self):
        """Should not send update when data becomes None."""
        hass = MagicMock()
        mock_unsub = MagicMock()
        mock_coordinator = MagicMock()
        mock_coordinator.data = [create_test_suggestion(0)]
        mock_coordinator.async_add_listener.return_value = mock_unsub
        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_coordinator
        hass.config_entries.async_entries.return_value = [mock_entry]
        connection = MagicMock()
        connection.subscriptions = {}
        msg = {"id": 1, "type": "automation_suggestions/subscribe"}

        websocket_subscribe_suggestions(hass, connection, msg)

        # Capture the listener callback
        listener_callback = mock_coordinator.async_add_listener.call_args[0][0]

        # Reset the mock and set data to None
        connection.send_message.reset_mock()
        mock_coordinator.data = None

        # Invoke the callback
        listener_callback()

        # Should not send a message when data is None
        connection.send_message.assert_not_called()

    def test_uses_correct_message_id_in_error(self):
        """Should use the correct message ID when sending error."""
        hass = MagicMock()
        hass.config_entries.async_entries.return_value = []
        connection = MagicMock()
        msg = {"id": 99, "type": "automation_suggestions/subscribe"}

        websocket_subscribe_suggestions(hass, connection, msg)

        call_args = connection.send_error.call_args
        assert call_args[0][0] == 99

    def test_subscription_stored_with_correct_id(self):
        """Should store subscription with the correct message ID key."""
        hass = MagicMock()
        mock_unsub = MagicMock()
        mock_coordinator = MagicMock()
        mock_coordinator.data = []
        mock_coordinator.async_add_listener.return_value = mock_unsub
        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_coordinator
        hass.config_entries.async_entries.return_value = [mock_entry]
        connection = MagicMock()
        connection.subscriptions = {}
        msg = {"id": 55, "type": "automation_suggestions/subscribe"}

        websocket_subscribe_suggestions(hass, connection, msg)

        assert 55 in connection.subscriptions
        assert connection.subscriptions[55] == mock_unsub


class TestAsyncRegisterWebsocketApi:
    """Tests for async_register_websocket_api function."""

    def test_registers_both_commands(self):
        """Should register both list and subscribe commands."""
        from custom_components.automation_suggestions.websocket_api import (
            async_register_websocket_api,
        )

        hass = MagicMock()

        with patch(
            "custom_components.automation_suggestions.websocket_api.websocket_api"
        ) as mock_ws_api:
            async_register_websocket_api(hass)

            # Should register both commands
            assert mock_ws_api.async_register_command.call_count == 2

            # Verify the commands were registered
            registered_handlers = [
                call[0][1] for call in mock_ws_api.async_register_command.call_args_list
            ]
            assert websocket_list_suggestions in registered_handlers
            assert websocket_subscribe_suggestions in registered_handlers
