"""Main Unigate entry point with high-level API."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any, Callable, TypeVar
from uuid import uuid4

from .events import KernelEvent
from .kernel import Exchange, Handler
from .message import Message
from .runtime import create_app, UnigateApp
from .stores import FileStores, InMemoryStores, NamespacedSecureStore, SQLiteStores


T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


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
        from .config import load_yaml
        config = load_yaml(config_path)
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
        from .plugins.base import get_registry
        
        plugin_dirs = cfg.get("unigate", {}).get("plugin_dirs", [])
        if plugin_dirs:
            from .plugins.base import register_plugin_dirs
            register_plugin_dirs(plugin_dirs)
        
        registry = get_registry()
        
        for instance_id, instance_config in instance_manager.items():
            channel_type = instance_config.get("type", "internal")
            
            channel_cls = registry.get_channel(channel_type)
            
            if channel_type == "internal":
                adapter = adapters_module.InternalAdapter(
                    instance_id=instance_id,
                    store=secure_store.for_instance(instance_id),
                    kernel=exchange,
                    config=instance_config,
                )
            elif channel_cls:
                adapter = channel_cls(
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
            
            fallback_instances = instance_config.get("fallback", [])
            runtime = exchange.register_instance(instance_id, adapter, fallback_instances=fallback_instances)
            retry_config = instance_config.get("retry", {})
            exchange.set_retry_policy(
                instance_id,
                max_attempts=retry_config.get("max_attempts", 5),
                retry_base_seconds=retry_config.get("base_delay_seconds", 2),
                retry_max_seconds=retry_config.get("max_delay_seconds", 30),
            )
        gate = cls(exchange=exchange, mount_prefix=cfg.get("unigate", {}).get("mount_prefix", "/unigate"))
        
        if cfg.get("routing"):
            exchange.setup_routing(cfg)
        
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
        self._message_handlers.append(handler)
        if self._exchange:
            self._exchange.set_handler(handler)
        return handler

    def on_event(self, event_name: str) -> Callable[[F], F]:
        """Decorator to register an event handler."""
        def decorator(func: F) -> F:
            if event_name not in self._event_handlers:
                self._event_handlers[event_name] = []
            self._event_handlers[event_name].append(func)
            if self._exchange:
                from .extensions import EventExtension
                ext = _EventHandlerExtension(event_name, func)
                self._exchange.add_event_extension(ext)
            return func
        return decorator

    def mount_to_app(self, app: Any, prefix: str | None = None) -> UnigateApp:
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
        asgi_app = create_app(self._exchange, mount_prefix=prefix)
        
        for instance_id, inst in self._exchange.instances.items():
            channel = inst.channel if hasattr(inst, "channel") else inst
            if hasattr(channel, "handle_web"):
                asgi_app.register_web_handler(instance_id, channel)
        
        if hasattr(app, "mount"):
            app.mount(prefix, asgi_app)
        return asgi_app

    def create_server_app(self, port: int = 8080) -> UnigateApp:
        """Create a standalone ASGI app for running with uvicorn."""
        if self._exchange is None:
            self._exchange = Exchange(
                inbox=InMemoryStores(),
                outbox=InMemoryStores(),
                sessions=InMemoryStores(),
                dedup=InMemoryStores(),
                interactions=InMemoryStores(),
            )
        app = create_app(self._exchange, mount_prefix=self._mount_prefix, port=port)
        
        for instance_id, inst in self._exchange.instances.items():
            channel = inst.channel if hasattr(inst, "channel") else inst
            if hasattr(channel, "handle_web"):
                app.register_web_handler(instance_id, channel)
        
        return app

    async def serve(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        """Run the exchange as a standalone server with uvicorn."""
        import uvicorn
        app = self.create_server(port)
        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()

    async def serve_forever(self) -> None:
        """Run the exchange until cancelled."""
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
