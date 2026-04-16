"""Main Unigate entry point with high-level API."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any, Callable, TypeVar
from uuid import uuid4

from .events import KernelEvent
from .kernel import Exchange, Handler
from .message import Message
from .runtime import UnigateASGIApp
from .stores import FileStores, InMemoryStores, NamespacedSecureStore, SQLiteStores


T = TypeVar("T")


class Unigate:
    """Main entry point for the unigate messaging exchange."""

    def __init__(
        self,
        exchange: Exchange | None = None,
        *,
        mount_prefix: str = "/unigate",
    ) -> None:
        self._exchange = exchange
        self._mount_prefix = mount_prefix
        self._message_handlers: list[Handler] = []
        self._event_handlers: dict[str, list[Callable[[KernelEvent], Any]]] = {}
        self._running = False

    @classmethod
    def from_config(cls, config_path: str) -> Unigate:
        """Create Unigate from a YAML config file."""
        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f)
        return cls.from_dict(config)

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> Unigate:
        """Create Unigate from a configuration dictionary."""
        from . import config as config_module
        cfg = config_module.load_config(config)
        storage_config = cfg.get("storage", {})
        backend = storage_config.get("backend", "memory")
        storage_path = storage_config.get("path", "./unigate_data")
        
        if backend == "memory":
            stores = InMemoryStores()
        elif backend == "sqlite":
            retention_days = storage_config.get("retention_days", 7)
            dedup_retention_days = storage_config.get("dedup_retention_days", 1)
            stores = SQLiteStores(
                storage_path, 
                retention_days=retention_days,
                dedup_retention_days=dedup_retention_days,
            )
        elif backend == "file":
            retention_days = storage_config.get("retention_days", 7)
            cleanup_interval = storage_config.get("cleanup_interval_seconds", 3600)
            stores = FileStores(
                base_path=storage_path,
                retention_days=retention_days,
                cleanup_interval_seconds=cleanup_interval,
            )
        else:
            stores = InMemoryStores()
        
        exchange = Exchange(
            inbox=stores,
            outbox=stores,
            sessions=stores,
            dedup=stores,
            interactions=stores,
            max_concurrency=cfg.get("unigate", {}).get("max_concurrent_processing", 64),
        )
        instance_manager = cfg.get("instances", {})
        secure_store = NamespacedSecureStore()
        from . import adapters as adapters_module
        for instance_id, instance_config in instance_manager.items():
            channel_type = instance_config.get("type", "internal")
            if channel_type == "internal":
                adapter = adapters_module.InternalAdapter(
                    instance_id=instance_id,
                    store=secure_store.for_instance(instance_id),
                    kernel=exchange,
                    config=instance_config,
                )
            else:
                adapter = adapters_module.FakeWebhookAdapter(
                    instance_id=instance_id,
                    store=secure_store.for_instance(instance_id),
                    kernel=exchange,
                    config=instance_config,
                )
            exchange.register_instance(instance_id, adapter)
            retry_config = instance_config.get("retry", {})
            exchange.set_retry_policy(
                instance_id,
                max_attempts=retry_config.get("max_attempts", 5),
                retry_base_seconds=retry_config.get("base_delay_seconds", 2),
                retry_max_seconds=retry_config.get("max_delay_seconds", 30),
            )
        gate = cls(exchange=exchange, mount_prefix=cfg.get("unigate", {}).get("mount_prefix", "/unigate"))
        for ext_config in cfg.get("extensions", []):
            from . import extensions as extensions_module
            ext = extensions_module.create_extension(ext_config)
            if ext:
                if isinstance(ext, extensions_module.InboundExtension):
                    exchange.add_inbound_extension(ext)
                if isinstance(ext, extensions_module.OutboundExtension):
                    exchange.add_outbound_extension(ext)
                if isinstance(ext, extensions_module.EventExtension):
                    exchange.add_event_extension(ext)
        return gate

    def on_message(
        self,
        handler: Callable[[Message], AsyncIterator[Message] | Message | list[Message] | None],
    ) -> Callable[[Message], AsyncIterator[Message] | Message | list[Message] | None]:
        """Decorator to register a message handler."""
        self._message_handlers.append(handler)  # type: ignore[arg-type]
        if self._exchange:
            self._exchange.set_handler(handler)
        return handler

    def on_event(self, event_name: str) -> Callable[[F], F]:
        """Decorator to register an event handler."""
        def decorator(func: F) -> F:
            if event_name not in self._event_handlers:
                self._event_handlers[event_name] = []
            self._event_handlers[event_name].append(func)  # type: ignore[arg-type]
            if self._exchange:
                from .extensions import EventExtension
                ext = _EventHandlerExtension(event_name, func)  # type: ignore[arg-type]
                self._exchange.add_event_extension(ext)
            return func
        return decorator  # type: ignore[return-value]

    def mount_to_app(self, app: Any, prefix: str | None = None) -> UnigateASGIApp:
        """Mount the unigate ASGI app into an existing ASGI application."""
        if self._exchange is None:
            self._exchange = Exchange(
                inbox=InMemoryStores(),
                outbox=InMemoryStores(),
                sessions=InMemoryStores(),
                dedup=InMemoryStores(),
                interactions=InMemoryStores(),
            )
        prefix = prefix or self._mount_prefix
        asgi_app = UnigateASGIApp(self._exchange, mount_prefix=prefix)
        if hasattr(app, "mount"):
            app.mount(prefix, asgi_app)
        return asgi_app

    async def serve(self) -> None:
        """Run the exchange as a standalone server."""
        if self._exchange is None:
            self._exchange = Exchange(
                inbox=InMemoryStores(),
                outbox=InMemoryStores(),
                sessions=InMemoryStores(),
                dedup=InMemoryStores(),
                interactions=InMemoryStores(),
            )
        self._running = True
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self._running = False


class _EventHandlerExtension:
    __slots__ = ("name", "handler", "priority")

    def __init__(self, name: str, handler: Callable[[KernelEvent], Any]) -> None:
        self.name = name
        self.handler = handler
        self.priority = 0

    async def handle(self, event: KernelEvent) -> None:
        if event.name == self.name:
            await self.handler(event)
