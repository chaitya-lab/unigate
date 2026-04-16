"""Fake channel adapter for testing."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from ..capabilities import ChannelCapabilities
from ..channel import BaseChannel, KernelHandle, SendResult
from ..events import KernelEvent
from ..lifecycle import HealthStatus, SetupResult, SetupStatus
from ..message import Action, Interactive, InteractiveResponse, MediaRef, Message, Reaction, Sender
from ..stores import SecureStore


class FakeChannel:
    name = "fake"
    transport = "internal"
    auth_method = "none"

    def __init__(
        self,
        instance_id: str,
        store: SecureStore | None = None,
        kernel: KernelHandle | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.instance_id = instance_id
        self.store = store or _FakeSecureStore()
        self.kernel = kernel
        self.config = config or {}
        self.sent: list[Message] = []
        self.fail_next_send: bool = False
        self._pending_responses: asyncio.Queue[Message] = asyncio.Queue()
        self._started = False

    async def setup(self) -> SetupResult:
        return SetupResult(status=SetupStatus.READY)

    async def start(self) -> None:
        self._started = True

    async def stop(self) -> None:
        self._started = False

    def to_message(self, raw: dict[str, Any]) -> Message:
        return Message(
            id=raw.get("id", str(uuid4())),
            session_id=raw.get("session_id", str(uuid4())),
            from_instance=self.instance_id,
            sender=Sender(
                platform_id=raw.get("sender_id", "user-1"),
                name=raw.get("sender_name", "Test User"),
                handle=raw.get("sender_handle"),
                is_bot=raw.get("is_bot", False),
            ),
            ts=raw.get("ts", datetime.now(UTC)),
            platform_id=raw.get("platform_id"),
            to=list(raw.get("to", [])),
            thread_id=raw.get("thread_id"),
            group_id=raw.get("group_id"),
            receiver_id=raw.get("receiver_id"),
            bot_mentioned=bool(raw.get("bot_mentioned", True)),
            text=raw.get("text"),
            media=[m if isinstance(m, MediaRef) else MediaRef(media_id=m.get("media_id", ""), type=m.get("type", "file")) for m in raw.get("media", [])],
            interactive=raw.get("interactive"),
            actions=[Action(type=a.get("type", ""), payload=a.get("payload", {})) for a in raw.get("actions", [])],
            reply_to_id=raw.get("reply_to_id"),
            reactions=[
                Reaction(emoji=r.get("emoji", ""), sender_id=r.get("sender_id", ""), ts=r.get("ts", datetime.now(UTC)))
                for r in raw.get("reactions", [])
            ],
            edit_of_id=raw.get("edit_of_id"),
            deleted_id=raw.get("deleted_id"),
            stream_id=raw.get("stream_id"),
            is_final=raw.get("is_final", True),
            raw=raw.get("raw", raw),
            metadata=raw.get("metadata", {}),
        )

    async def from_message(self, msg: Message) -> SendResult:
        if self.fail_next_send:
            self.fail_next_send = False
            return SendResult(success=False, error="simulated failure")
        self.sent.append(msg)
        await self._pending_responses.put(msg)
        return SendResult(success=True, provider_message_id=f"sent:{msg.id}")

    async def inject(
        self,
        text: str | None = None,
        *,
        sender_id: str = "user-1",
        sender_name: str = "Test User",
        sender_handle: str | None = None,
        session_id: str | None = None,
        group_id: str | None = None,
        thread_id: str | None = None,
        bot_mentioned: bool = True,
        interactive_response: InteractiveResponse | None = None,
        **extra: Any,
    ) -> Message:
        raw: dict[str, Any] = {
            "id": str(uuid4()),
            "session_id": session_id or str(uuid4()),
            "sender_id": sender_id,
            "sender_name": sender_name,
            "sender_handle": sender_handle,
            "bot_mentioned": bot_mentioned,
            "group_id": group_id,
            "thread_id": thread_id,
            "text": text,
            **extra,
        }
        if interactive_response:
            raw["interactive"] = Interactive(
                interaction_id=str(uuid4()),
                type="response",
                prompt="",
                response=interactive_response,
            )
        msg = self.to_message(raw)
        if self.kernel is not None:
            await self.kernel.ingest(self.instance_id, raw)
        return msg

    async def next_sent(self, timeout: float = 1.0) -> Message | None:
        try:
            return await asyncio.wait_for(self._pending_responses.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    @property
    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(
            direction="bidirectional",
            supports_groups=True,
            supports_threads=True,
            supports_reactions=True,
            supports_reply_to=True,
            supports_edit=True,
            supports_delete=True,
            supports_typing_indicator=True,
            supports_media_send=True,
            max_message_length=4096,
        )

    async def reset_setup(self) -> None:
        pass

    async def health_check(self) -> HealthStatus:
        return HealthStatus.HEALTHY if self._started else HealthStatus.UNKNOWN

    async def background_tasks(self) -> list[object]:
        return []

    async def verify_signature(self, request: Any) -> bool:
        return True


class _FakeSecureStore:
    _values: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._values.get(key)

    async def set(self, key: str, value: str) -> None:
        self._values[key] = value

    async def delete(self, key: str) -> None:
        self._values.pop(key, None)
