"""WebSocket API for Automation Suggestions."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import AutomationSuggestionsCoordinator

_LOGGER = logging.getLogger(__name__)


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register WebSocket API handlers."""
    websocket_api.async_register_command(hass, websocket_list_suggestions)
    websocket_api.async_register_command(hass, websocket_subscribe_suggestions)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "automation_suggestions/list",
        vol.Optional("page", default=1): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional("page_size", default=20): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
    }
)
@callback
def websocket_list_suggestions(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Handle list suggestions WebSocket command."""
    coordinator = _get_coordinator(hass)
    if coordinator is None or coordinator.data is None:
        connection.send_result(msg["id"], {"suggestions": [], "total": 0, "page": 1, "pages": 0})
        return

    suggestions = coordinator.data
    total = len(suggestions)
    page = msg["page"]
    page_size = msg["page_size"]
    pages = (total + page_size - 1) // page_size if total > 0 else 0

    start = (page - 1) * page_size
    end = start + page_size
    page_suggestions = [s.to_dict() for s in suggestions[start:end]]

    connection.send_result(
        msg["id"],
        {
            "suggestions": page_suggestions,
            "total": total,
            "page": page,
            "pages": pages,
            "page_size": page_size,
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "automation_suggestions/subscribe",
    }
)
@callback
def websocket_subscribe_suggestions(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Subscribe to suggestion updates."""
    coordinator = _get_coordinator(hass)
    if coordinator is None:
        connection.send_error(msg["id"], "not_found", "Coordinator not found")
        return

    @callback
    def async_on_update() -> None:
        """Send update when coordinator data changes."""
        if coordinator.data is None:
            return
        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                {
                    "suggestions": [s.to_dict() for s in coordinator.data],
                    "total": len(coordinator.data),
                },
            )
        )

    # Subscribe to coordinator updates
    unsub = coordinator.async_add_listener(async_on_update)
    connection.subscriptions[msg["id"]] = unsub

    # Send initial data
    connection.send_result(msg["id"])
    async_on_update()


def _get_coordinator(hass: HomeAssistant) -> AutomationSuggestionsCoordinator | None:
    """Get coordinator from hass data."""
    entries = hass.config_entries.async_entries(DOMAIN)
    for entry in entries:
        if hasattr(entry, "runtime_data") and entry.runtime_data is not None:
            return entry.runtime_data
    return None
