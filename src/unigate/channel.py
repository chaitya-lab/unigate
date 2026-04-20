"""Base adapter and kernel-facing protocols."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Protocol

from .capabilities import ChannelCapabilities
from .events import KernelEvent
from .lifecycle import HealthStatus, SetupResult
from .message import Interactive, Message


def parse_degraded_response(msg: Message, text: str) -> Message | None:
    """Parse text response from degraded interactive message.
    
    When user responds to a degraded (text) interactive, this parses the text
    and populates the interactive.response field so handler receives structured data.
    
    Returns modified message with interactive.response set.
    """
    if msg.interactive and msg.interactive.response:
        return None
    
    original_interaction_id = msg.metadata.get("original_interaction_id")
    if not original_interaction_id:
        return None
    
    from .message import InteractiveResponse, InteractionType
    
    return Message(
        id=msg.id,
        session_id=msg.session_id,
        from_instance=msg.from_instance,
        sender=msg.sender,
        ts=msg.ts,
        platform_id=msg.platform_id,
        to=msg.to,
        thread_id=msg.thread_id,
        group_id=msg.group_id,
        receiver_id=msg.receiver_id,
        bot_mentioned=msg.bot_mentioned,
        text=text,
        media=msg.media,
        interactive=Interactive(
            interaction_id=original_interaction_id,
            type=InteractionType.CONFIRM,
            prompt="",
            response=InteractiveResponse(
                interaction_id=original_interaction_id,
                type=InteractionType.CONFIRM,
                value=text,
                raw={},
            ),
        ),
        actions=msg.actions,
        reply_to_id=msg.reply_to_id,
        reactions=msg.reactions,
        edit_of_id=msg.edit_of_id,
        deleted_id=msg.deleted_id,
        stream_id=msg.stream_id,
        is_final=msg.is_final,
        raw=msg.raw,
        metadata={},
    )


def degrade_interactive(msg: Message, supported_types: list[str]) -> Message | None:
    """Convert interactive message to text if channel doesn't support it.
    
    Returns modified message with text instead of interactive, or None if degradation not possible.
    
    Usage in channel's from_message():
        if msg.interactive:
            degraded = degrade_interactive(msg, self.capabilities.supported_interaction_types)
            if degraded:
                msg = degraded
    """
    if not msg.interactive:
        return None
    
    interaction = msg.interactive
    supported = set(supported_types) if supported_types else set()
    
    if interaction.type in supported:
        return None
    
    prompt = interaction.prompt
    if interaction.options:
        options_str = " / ".join(interaction.options)
        prompt = f"{prompt} ({options_str})"
    
    return Message(
        id=msg.id,
        session_id=msg.session_id,
        from_instance=msg.from_instance,
        sender=msg.sender,
        ts=msg.ts,
        platform_id=msg.platform_id,
        to=msg.to,
        thread_id=msg.thread_id,
        group_id=msg.group_id,
        receiver_id=msg.receiver_id,
        bot_mentioned=msg.bot_mentioned,
        text=prompt,
        media=msg.media,
        interactive=None,
        actions=msg.actions,
        reply_to_id=msg.reply_to_id,
        reactions=msg.reactions,
        edit_of_id=msg.edit_of_id,
        deleted_id=msg.deleted_id,
        stream_id=msg.stream_id,
        is_final=msg.is_final,
        raw=msg.raw,
        metadata={**msg.metadata, "degraded_interactive": True, "original_interaction_id": interaction.interaction_id},
    )


class SecureStore(Protocol):
    """Namespaced credential storage for one instance."""

    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str) -> None: ...
    async def delete(self, key: str) -> None: ...


class KernelHandle(Protocol):
    """Small kernel surface exposed to adapters."""

    async def emit_event(self, event: KernelEvent) -> None: ...
    async def ingest(self, instance_id: str, raw: dict[str, Any]) -> str: ...


@dataclass(slots=True)
class RawRequest:
    """Generic incoming HTTP request shape for signature verification."""

    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    query: dict[str, str] = field(default_factory=dict)
    path_params: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class SendResult:
    """Normalized send outcome returned by adapters."""

    success: bool
    provider_message_id: str | None = None
    error: str | None = None


class BaseChannel(Protocol):
    """The only adapter contract that matters."""

    name: ClassVar[str]
    transport: ClassVar[str]
    auth_method: ClassVar[str]

    instance_id: str
    config: dict[str, Any]
    store: SecureStore
    kernel: KernelHandle

    async def setup(self) -> SetupResult:
        """Authenticate and prepare the instance."""

    async def start(self) -> None:
        """Begin receiving from the transport."""

    async def stop(self) -> None:
        """Disconnect gracefully."""

    def to_message(self, raw: dict[str, Any]) -> Message:
        """Convert transport payload to a universal message."""

    async def from_message(self, msg: Message) -> SendResult:
        """Convert universal message to transport send."""

    @property
    def capabilities(self) -> ChannelCapabilities:
        """Declared adapter capabilities."""

    async def reset_setup(self) -> None:
        """Optional auth reset hook."""

    async def health_check(self) -> HealthStatus:
        """Optional health signal."""

    async def background_tasks(self) -> list[object]:
        """Optional long-running tasks owned by the adapter."""

    async def verify_signature(self, request: RawRequest) -> bool:
        """Optional HTTP verification hook."""
