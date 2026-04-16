"""Channel capability declarations."""

from __future__ import annotations

from dataclasses import dataclass, field

from .message import MediaType


@dataclass(slots=True)
class ChannelCapabilities:
    """Declared capabilities for one adapter."""

    direction: str
    supports_threads: bool = False
    supports_reactions: bool = False
    supports_groups: bool = False
    supports_reply_to: bool = False
    supports_edit: bool = False
    supports_delete: bool = False
    supports_typing_indicator: bool = False
    supports_media_send: bool = True
    supported_media_types: list[MediaType] = field(default_factory=list)
    supported_interaction_types: list[str] = field(default_factory=list)
    max_message_length: int = 4096
    max_media_size_bytes: int | None = None
    streaming_mode: str = "none"
