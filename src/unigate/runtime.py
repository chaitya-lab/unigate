"""Mountable ASGI runtime surface."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from .kernel import Exchange


class UnigateASGIApp:
    def __init__(
        self, 
        exchange: Exchange, 
        mount_prefix: str = "/unigate",
        health_check_interval: float = 60.0,
    ) -> None:
        self.exchange = exchange
        self.mount_prefix = mount_prefix.rstrip("/")
        self.health_check_interval = health_check_interval
        self._health_task: asyncio.Task | None = None
    
    async def start_health_checks(self) -> None:
        """Start background health check task."""
        if self._health_task is None:
            self._health_task = asyncio.create_task(
                self.exchange.health_check_loop(self.health_check_interval)
            )
    
    async def stop_health_checks(self) -> None:
        """Stop background health check task."""
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
            self._health_task = None

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self._respond(send, 404, {"error": "unsupported"})
            return
        path = str(scope.get("path", ""))
        method = str(scope.get("method", "GET")).upper()
        
        # Start health checks on first request
        if self._health_task is None:
            asyncio.create_task(self.start_health_checks())
        
        if path == f"{self.mount_prefix}/status" and method == "GET":
            instances = self.exchange.instance_manager.status()
            payload = {
                "instances": list(self.exchange.instances.keys()),
                "instances_detail": instances,
            }
            await self._respond(send, 200, payload)
            return
        
        if path == f"{self.mount_prefix}/health" and method == "GET":
            health = await self.exchange.check_health()
            all_healthy = all(s == "healthy" for s in health.values())
            payload = {
                "ok": all_healthy,
                "instances": health,
            }
            await self._respond(send, 200, payload)
            return
        
        # Per-instance health
        instance_health_prefix = f"{self.mount_prefix}/health/"
        if path.startswith(instance_health_prefix) and method == "GET":
            instance_id = path[len(instance_health_prefix):]
            if instance_id in self.exchange.instances:
                from .lifecycle import HealthStatus
                health = await self.exchange.instance_manager.health(instance_id)
                payload = {"ok": health == HealthStatus.HEALTHY, "status": health.value}
                await self._respond(send, 200, payload)
            else:
                await self._respond(send, 404, {"error": "instance not found"})
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
