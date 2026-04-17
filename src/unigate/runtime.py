"""Mountable ASGI runtime with unified routing."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from .kernel import Exchange


class UnigateApp:
    @asynccontextmanager
    async def lifespan(self):
        """Uvicorn lifespan - start/stop with event loop."""
        # Do setup first (synchronous part done in CLI)
        await self.start()  # This has event loop, so can create tasks
        yield
        await self.stop()

    def __init__(
        self,
        exchange: Exchange,
        mount_prefix: str = "/unigate",
        port: int = 8080,
    ) -> None:
        self.exchange = exchange
        self.mount_prefix = mount_prefix.rstrip("/")
        self.port = port
        self._health_task: asyncio.Task | None = None
        self._cleanup_task: asyncio.Task | None = None
        self._outbox_task: asyncio.Task | None = None
        self._webui_channels: dict[str, Any] = {}

    async def start(self) -> None:
        """Start background tasks and setup all channels."""
        for instance_id, inst in self.exchange.instances.items():
            channel = inst.channel if hasattr(inst, "channel") else inst
            if hasattr(channel, 'setup'):
                try:
                    result = await channel.setup()
                    print(f"[UNIGATE] Setup {instance_id}")
                except Exception as e:
                    print(f"[UNIGATE] Setup {instance_id} failed: {e}")
        
        # Start background tasks (non-blocking)
        if hasattr(self.exchange, 'start_health_check_loop'):
            self._health_task = asyncio.create_task(
                self.exchange.start_health_check_loop(60.0)
            )
        
        # Start channels in background
        for instance_id, inst in self.exchange.instances.items():
            channel = inst.channel if hasattr(inst, "channel") else inst
            if hasattr(channel, 'start'):
                try:
                    asyncio.create_task(channel.start())
                    print(f"[UNIGATE] Started {instance_id}")
                except Exception as e:
                    print(f"[UNIGATE] Start {instance_id} failed: {e}")
        
        if hasattr(self.exchange, 'start_health_check_loop'):
            if self._health_task is None:
                self._health_task = asyncio.create_task(
                    self.exchange.start_health_check_loop(60.0)
                )
        if hasattr(self.exchange, 'start_cleanup_task'):
            if self._cleanup_task is None:
                self._cleanup_task = asyncio.create_task(
                    self.exchange.start_cleanup_task()
                )
        if hasattr(self.exchange, 'start_outbox_flush_loop'):
            if self._outbox_task is None:
                self.exchange.start_outbox_flush_loop(1.0)
                self._outbox_task = self.exchange._outbox_flush_task

    async def stop(self) -> None:
        """Stop background tasks."""
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
            self._health_task = None
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        if self._outbox_task:
            self._outbox_task.cancel()
            try:
                await self._outbox_task
            except asyncio.CancelledError:
                pass
            self._outbox_task = None

    def register_webui(self, instance_id: str, channel: Any) -> None:
        """Register a webui channel for serving."""
        self._webui_channels[instance_id] = channel

    async def _handle_lifespan(self, receive: Any, send: Any) -> None:
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await self.start()
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await self.stop()
                await send({"type": "lifespan.shutdown.complete"})
                break

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        # Handle lifespan protocol
        if scope["type"] == "lifespan":
            await self._handle_lifespan(receive, send)
            return
        if scope["type"] != "http":
            await self._error(send, 404, "unsupported")
            return

        path = scope.get("path", "")
        method = str(scope.get("method", "GET")).upper()

        if self._health_task is None:
            asyncio.create_task(self.start())

        if path == f"{self.mount_prefix}/status":
            await self._status(send)
            return

        if path == f"{self.mount_prefix}/health":
            await self._health(send)
            return

        if path == f"{self.mount_prefix}/instances":
            await self._instances(send)
            return

        webhook_prefix = f"{self.mount_prefix}/webhook/"
        if path.startswith(webhook_prefix) and method == "POST":
            instance_id = path[len(webhook_prefix):].split("/")[0]
            await self._webhook(instance_id, scope, receive, send)
            return

        web_prefix = f"{self.mount_prefix}/web/"
        if path.startswith(web_prefix):
            instance_id = path[len(web_prefix):].split("/")[0]
            await self._webui(instance_id, scope, receive, send)
            return

        await self._error(send, 404, "not_found")

    async def _status(self, send: Any) -> None:
        instances = {}
        stats = {
            "inbox_count": 0,
            "outbox_count": 0,
            "sessions_count": 0,
            "interactions_count": 0,
        }

        for name, inst in self.exchange.instances.items():
            channel = inst.channel if hasattr(inst, "channel") else inst
            state = "unknown"
            if hasattr(channel, "state"):
                state = channel.state.value if hasattr(channel.state, "value") else str(channel.state)
            elif hasattr(channel, "health_check"):
                state = "active"
            else:
                state = "active"

            instances[name] = {
                "state": state,
                "type": getattr(channel, "name", "unknown"),
            }

            if hasattr(channel, "_sent") and isinstance(getattr(channel, "_sent"), list):
                instances[name]["messages_sent"] = len(channel._sent)

        if hasattr(self.exchange, "_inbox_events"):
            stats["inbox_count"] = len(getattr(self.exchange, "_inbox_events", []))

        payload = {
            "ok": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "instances": instances,
            "stats": stats,
        }
        await self._json(send, 200, payload)

    async def _health(self, send: Any) -> None:
        health = {}
        for name, inst in self.exchange.instances.items():
            channel = inst.channel if hasattr(inst, "channel") else inst
            try:
                if hasattr(channel, "health_check"):
                    result = await channel.health_check()
                    health[name] = result.value if hasattr(result, "value") else str(result)
                else:
                    health[name] = "healthy"
            except Exception:
                health[name] = "unhealthy"

        all_healthy = all(s == "healthy" for s in health.values())
        payload = {
            "ok": all_healthy,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "instances": health,
        }
        await self._json(send, 200, payload)

    async def _instances(self, send: Any) -> None:
        rows = []
        for name, inst in self.exchange.instances.items():
            channel = inst.channel if hasattr(inst, "channel") else inst
            state = "unknown"
            msg_in = "-"
            msg_out = "-"

            if hasattr(channel, "state"):
                state = channel.state.value if hasattr(channel.state, "value") else str(channel.state)
            elif hasattr(channel, "health_check"):
                state = "active"

            if hasattr(channel, "_sent") and isinstance(getattr(channel, "_sent"), list):
                msg_out = len(channel._sent)

            rows.append({
                "instance": name,
                "state": state,
                "type": getattr(channel, "name", "unknown"),
                "messages_in": msg_in,
                "messages_out": msg_out,
            })

        payload = {
            "instances": rows,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self._json(send, 200, payload)

    async def _webhook(self, instance_id: str, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if instance_id not in self.exchange.instances:
            await self._error(send, 404, f"instance '{instance_id}' not found")
            return

        body = await self._read_body(receive)
        raw = json.loads(body.decode("utf-8") or "{}")

        status = await self.exchange.ingest(instance_id, raw)
        await self._json(send, 200, {"status": status})

    async def _webui(self, instance_id: str, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if instance_id not in self._webui_channels:
            await self._error(send, 404, f"webui '{instance_id}' not found")
            return

        channel = self._webui_channels[instance_id]
        prefix = f"{self.mount_prefix}/web/{instance_id}"
        path = scope.get("path", "")
        if path.startswith(prefix):
            path = path[len(prefix):] or "/"
        new_scope = dict(scope)
        new_scope["path"] = path
        await channel.handle_web(new_scope, receive, send)

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

    async def _json(self, send: Any, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, default=str).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [[b"content-type", b"application/json"]],
        })
        await send({"type": "http.response.body", "body": data, "more_body": False})

    async def _error(self, send: Any, status: int, message: str) -> None:
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [[b"content-type", b"text/plain"]],
        })
        await send({"type": "http.response.body", "body": message.encode(), "more_body": False})


def create_app(
    exchange: Exchange,
    mount_prefix: str = "/unigate",
    port: int = 8080,
) -> UnigateApp:
    """Create a Unigate ASGI app."""
    app = UnigateApp(exchange, mount_prefix, port)
    return app


UnigateASGIApp = UnigateApp
