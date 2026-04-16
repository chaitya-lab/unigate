"""HTTP transport for webhook delivery."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from ..message import Message

from .base import TransportProtocol


class HTTPTransport(TransportProtocol):
    """Send messages via HTTP/HTTPS."""

    name = "http"

    async def send(self, msg: Message, config: dict[str, Any]) -> bool:
        """Send message as HTTP POST request."""
        url = config.get("url")
        if not url:
            return False

        method = config.get("method", "POST").upper()
        headers = config.get("headers", {})
        auth = config.get("auth")
        timeout = config.get("timeout", 30)

        payload = self._build_payload(msg, config)

        auth_httpx = None
        if auth:
            if isinstance(auth, dict):
                if auth.get("type") == "bearer":
                    auth_httpx = httpx.Auth(
                        lambda request: request.headers.update(
                            {"Authorization": f"Bearer {auth['token']}"}
                        )
                    )
            elif isinstance(auth, tuple):
                auth_httpx = httpx.BasicAuth(auth[0], auth[1])

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                if method == "GET":
                    response = await client.get(url, headers=headers, params=payload)
                else:
                    response = await client.post(url, headers=headers, json=payload)
                return 200 <= response.status_code < 300
        except Exception:
            return False

    def _build_payload(self, msg: Message, config: dict[str, Any]) -> dict[str, Any]:
        format_type = config.get("format", "message")

        if format_type == "message":
            return {
                "id": msg.id,
                "text": msg.text,
                "sender": {
                    "id": msg.sender.platform_id,
                    "name": msg.sender.name,
                },
                "session_id": msg.session_id,
            }
        elif format_type == "telegram":
            return {
                "chat_id": config.get("chat_id"),
                "text": msg.text,
            }
        elif format_type == "slack":
            return {
                "text": msg.text,
                "channel": config.get("channel"),
            }
        else:
            return {"text": msg.text}


class WebhookTransport(HTTPTransport):
    """Alias for HTTP transport (backward compatibility)."""

    name = "webhook"
