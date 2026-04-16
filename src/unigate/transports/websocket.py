"""WebSocket transport for real-time delivery."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

try:
    import websockets
except ImportError:
    websockets = None

if TYPE_CHECKING:
    from ..message import Message

from .base import TransportProtocol


class WebSocketTransport(TransportProtocol):
    """Send messages via WebSocket."""

    name = "websocket"

    async def send(self, msg: Message, config: dict[str, Any]) -> bool:
        """Send message over WebSocket connection."""
        if websockets is None:
            return False

        uri = config.get("uri")
        if not uri:
            return False

        auth = config.get("auth")
        headers = config.get("headers", {})
        timeout = config.get("timeout", 30)
        format_type = config.get("format", "json")

        payload = self._build_payload(msg, format_type)

        extra_headers = {}
        if auth:
            if auth.get("type") == "bearer":
                headers["Authorization"] = f"Bearer {auth['token']}"
            elif auth.get("type") == "api_key":
                key_name = auth.get("key_name", "X-API-Key")
                headers[key_name] = auth["key"]

        try:
            async with websockets.connect(
                uri, extra_headers=headers
            ) as ws:
                await ws.send(payload)
                return True
        except Exception:
            return False

    def _build_payload(self, msg: Message, format_type: str) -> str:
        if format_type == "json":
            return json.dumps(
                {
                    "id": msg.id,
                    "text": msg.text,
                    "sender": {
                        "id": msg.sender.platform_id,
                        "name": msg.sender.name,
                    },
                    "session_id": msg.session_id,
                }
            )
        else:
            return msg.text or ""


class SSETransport(TransportProtocol):
    """Server-Sent Events transport (one-way)."""

    name = "sse"

    async def send(self, msg: Message, config: dict[str, Any]) -> bool:
        """Send message as SSE event."""
        uri = config.get("uri")
        if not uri:
            return False

        event_type = config.get("event", "message")
        retry = config.get("retry", 5000)

        try:
            import httpx

            data = f"event: {event_type}\n"
            data += f"retry: {retry}\n"
            data += f"data: {json.dumps({'text': msg.text, 'id': msg.id})}\n\n"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    uri, content=data, headers={"Content-Type": "text/event-stream"}
                )
                return 200 <= response.status_code < 300
        except Exception:
            return False
