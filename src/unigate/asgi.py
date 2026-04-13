"""Minimal ASGI integration for unigate."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from .channels.api import ApiChannel
from .channels.web import WebChannel
from .channels.websocket_server import WebSocketServerChannel
from .gate import Unigate


Scope = dict[str, Any]
Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]


class UnigateASGIApp:
    """Mountable ASGI app for api, web, and websocket channels."""

    def __init__(self, gate: Unigate, prefix: str = "/unigate") -> None:
        self.gate = gate
        normalized = prefix.rstrip("/")
        self.prefix = normalized or ""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope_type = scope["type"]
        path = scope.get("path", "")
        if scope_type == "http":
            await self._handle_http(path, scope, receive, send)
            return
        if scope_type == "websocket":
            await self._handle_websocket(path, scope, receive, send)
            return

        raise RuntimeError(f"Unsupported ASGI scope type: {scope_type}")

    async def _handle_http(self, path: str, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("method") != "POST":
            await self._json_response(send, 405, {"error": "method_not_allowed"})
            return

        route = self._relative_path(path)
        if route is None:
            await self._json_response(send, 404, {"error": "not_found"})
            return

        payload = await self._read_json_body(receive)
        if route[:3] == ["channels", "api", *route[2:3]] and len(route) == 4 and route[3] == "messages":
            await self._handle_api_http(route[2], payload, send)
            return
        if route[:3] == ["channels", "web", *route[2:3]] and len(route) == 4 and route[3] == "messages":
            await self._handle_web_http(route[2], payload, send)
            return

        await self._json_response(send, 404, {"error": "not_found"})

    async def _handle_api_http(self, instance_id: str, payload: dict[str, Any], send: Send) -> None:
        channel = self.gate.instances.get(instance_id).channel
        if not isinstance(channel, ApiChannel):
            await self._json_response(send, 400, {"error": "wrong_channel_type"})
            return

        before = len(channel.sent_messages)
        message = await channel.receive_request(
            request_id=payload["request_id"],
            client_id=payload["client_id"],
            sender_name=payload["sender_name"],
            text=payload["text"],
            conversation_id=payload["conversation_id"],
        )
        reply = channel.sent_messages[before] if len(channel.sent_messages) > before else None
        await self._json_response(
            send,
            200,
            {
                "message_id": message.id,
                "session_id": message.session_id,
                "reply_text": None if reply is None else reply.text,
            },
        )

    async def _handle_web_http(self, instance_id: str, payload: dict[str, Any], send: Send) -> None:
        channel = self.gate.instances.get(instance_id).channel
        if not isinstance(channel, WebChannel):
            await self._json_response(send, 400, {"error": "wrong_channel_type"})
            return

        before = len(channel.sent_messages)
        message = await channel.receive_browser_message(
            message_id=payload["message_id"],
            browser_session_id=payload["browser_session_id"],
            visitor_id=payload["visitor_id"],
            visitor_name=payload["visitor_name"],
            text=payload["text"],
        )
        reply = channel.sent_messages[before] if len(channel.sent_messages) > before else None
        await self._json_response(
            send,
            200,
            {
                "message_id": message.id,
                "session_id": message.session_id,
                "reply_text": None if reply is None else reply.text,
            },
        )

    async def _handle_websocket(self, path: str, scope: Scope, receive: Receive, send: Send) -> None:
        route = self._relative_path(path)
        if route is None or len(route) != 3 or route[0] != "channels" or route[1] != "ws":
            await send({"type": "websocket.close", "code": 1008})
            return

        instance_id = route[2]
        channel = self.gate.instances.get(instance_id).channel
        if not isinstance(channel, WebSocketServerChannel):
            await send({"type": "websocket.close", "code": 1008})
            return

        event = await receive()
        if event["type"] != "websocket.connect":
            await send({"type": "websocket.close", "code": 1008})
            return
        await send({"type": "websocket.accept"})

        while True:
            event = await receive()
            if event["type"] == "websocket.disconnect":
                return
            if event["type"] != "websocket.receive":
                continue

            text = event.get("text")
            if text is None:
                await send({"type": "websocket.send", "text": json.dumps({"error": "text_required"})})
                continue

            payload = json.loads(text)
            before = len(channel.sent_messages)
            message = await channel.receive_frame(
                frame_id=payload["frame_id"],
                connection_id=payload["connection_id"],
                sender_id=payload["sender_id"],
                sender_name=payload["sender_name"],
                text=payload["text"],
            )
            reply = channel.sent_messages[before] if len(channel.sent_messages) > before else None
            await send(
                {
                    "type": "websocket.send",
                    "text": json.dumps(
                        {
                            "message_id": message.id,
                            "session_id": message.session_id,
                            "reply_text": None if reply is None else reply.text,
                        }
                    ),
                }
            )

    def _relative_path(self, path: str) -> list[str] | None:
        prefix = self.prefix
        if prefix and not path.startswith(prefix):
            return None
        relative = path[len(prefix) :] if prefix else path
        parts = [part for part in relative.split("/") if part]
        return parts

    async def _read_json_body(self, receive: Receive) -> dict[str, Any]:
        body = bytearray()
        more_body = True
        while more_body:
            event = await receive()
            body.extend(event.get("body", b""))
            more_body = event.get("more_body", False)
        return json.loads(body.decode("utf-8") or "{}")

    async def _json_response(self, send: Send, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": body, "more_body": False})


def create_asgi_app(gate: Unigate, prefix: str = "/unigate") -> UnigateASGIApp:
    """Create a mountable ASGI app for the current gate instance."""

    return UnigateASGIApp(gate=gate, prefix=prefix)
