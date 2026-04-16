"""Test kit for unigate testing."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar
from uuid import uuid4

from ..events import KernelEvent
from ..kernel import Exchange
from ..message import Message
from ..stores import InMemoryStores, NamespacedSecureStore
from .fake_channel import FakeChannel


F = TypeVar("F", bound=Callable[..., Awaitable[Any] | Any])


class TestKit:
    def __init__(
        self,
        *,
        max_concurrency: int = 64,
        stores: InMemoryStores | None = None,
    ) -> None:
        self._stores = stores or InMemoryStores()
        self._exchange = Exchange(
            inbox=self._stores,
            outbox=self._stores,
            sessions=self._stores,
            dedup=self._stores,
            interactions=self._stores,
            max_concurrency=max_concurrency,
        )
        self._channels: dict[str, FakeChannel] = {}
        self._handler: Callable[[Message], Awaitable[Message | list[Message] | None] | Message | list[Message] | None] | None = None
        self._event_handlers: dict[str, list[Callable[[KernelEvent], Awaitable[bool] | bool]]] = {}
        self._running = False

    def add_instance(self, channel: FakeChannel | None = None, *, instance_id: str | None = None) -> FakeChannel:
        if channel is None:
            instance_id = instance_id or str(uuid4())
            channel = FakeChannel(instance_id=instance_id)
        instance_id = instance_id or channel.instance_id
        store = NamespacedSecureStore().for_instance(instance_id)
        channel.instance_id = instance_id
        channel.kernel = self._exchange
        self._channels[instance_id] = channel
        self._exchange.register_instance(instance_id, channel)
        return channel

    def on_message(
        self,
        handler: Callable[[Message], Awaitable[Message | list[Message] | None] | Message | list[Message] | None],
    ) -> None:
        self._handler = handler
        self._exchange.set_handler(handler)

    def on_event(self, event_name: str) -> Callable[[F], F]:
        def decorator(func: F) -> F:
            if event_name not in self._event_handlers:
                self._event_handlers[event_name] = []
            self._event_handlers[event_name].append(func)  # type: ignore[arg-type]
            return func
        return decorator

    async def start(self) -> None:
        self._running = True
        for channel in self._channels.values():
            await channel.start()

    async def stop(self) -> None:
        self._running = False
        for channel in self._channels.values():
            await channel.stop()

    def reset(self) -> None:
        self._stores.inbox.clear()
        self._stores.outbox.clear()
        self._stores.sessions.clear()
        self._stores.dedup.clear()
        self._stores.dead_letters.clear()
        self._stores.pending_interactions.clear()
        self._exchange.events.clear()
        for channel in self._channels.values():
            channel.sent.clear()

    @property
    def exchange(self) -> Exchange:
        return self._exchange

    @property
    def stores(self) -> InMemoryStores:
        return self._stores

    def get_channel(self, instance_id: str) -> FakeChannel | None:
        return self._channels.get(instance_id)

    async def ingest(self, instance_id: str, raw: dict[str, Any]) -> str:
        return await self._exchange.ingest(instance_id, raw)

    async def flush_outbox(self) -> None:
        await self._exchange.flush_outbox()
