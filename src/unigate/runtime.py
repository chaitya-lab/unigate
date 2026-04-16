"""Mountable ASGI runtime surface."""

from __future__ import annotations

import json
from typing import Any

from .kernel import Exchange


class UnigateASGIApp:
    def __init__(self, exchange: Exchange, mount_prefix: str = "/unigate") -> None:
        self.exchange = exchange
        self.mount_prefix = mount_prefix.rstrip("/")

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self._respond(send, 404, {"error": "unsupported"})
            return
        path = str(scope.get("path", ""))
        method = str(scope.get("method", "GET")).upper()
        if path == f"{self.mount_prefix}/status" and method == "GET":
            payload = {"instances": list(self.exchange.instances.keys())}
            await self._respond(send, 200, payload)
            return
        if path == f"{self.mount_prefix}/health" and method == "GET":
            payload = {"ok": True, "events": len(self.exchange.events)}
            await self._respond(send, 200, payload)
            return
        webhook_prefix = f"{self.mount_prefix}/webhook/"
        if path.startswith(webhook_prefix) and method == "POST":
            instance_id = path[len(webhook_prefix) :]
            body = await self._read_body(receive)
            raw = json.loads(body.decode("utf-8") or "{}")
            status = await self.exchange.ingest(instance_id, raw)
            await self._respond(send, 200, {"status": status})
            return
        await self._respond(send, 404, {"error": "not_found"})

    async def _read_body(self, receive: Any) -> bytes:
        parts: list[bytes] = []
        while True:
            message = await receive()
            if message["type"] != "http.request":
                break
            parts.append(bytes(message.get("body", b"")))
            if not message.get("more_body", False):
                break
        return b"".join(parts)

    async def _respond(self, send: Any, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": data, "more_body": False})
