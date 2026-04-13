"""Normalized inbound and outbound message contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .interactive import InteractivePayload


class MediaType(str, Enum):
    """Transport-neutral media categories."""

    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    VOICE = "voice"
    FILE = "file"
    STICKER = "sticker"
    LOCATION = "location"
    CONTACT = "contact"


class ChannelActionType(str, Enum):
    """Normalized outbound side-effect actions."""

    TYPING_ON = "typing_on"
    TYPING_OFF = "typing_off"
    REACTION_ADD = "reaction_add"
    MESSAGE_EDIT = "message_edit"
    MESSAGE_DELETE = "message_delete"


@dataclass(slots=True)
class MediaRef:
    """Reference to media that can be resolved lazily by the adapter."""

    media_id: str
    type: MediaType
    mime_type: str | None = None
    size_bytes: int | None = None
    filename: str | None = None
    duration_seconds: float | None = None
    dimensions: tuple[int, int] | None = None
    thumbnail_url: str | None = None
    full_url: str | None = None
    resolved: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Reaction:
    """Reaction attached to a message at observation time."""

    key: str
    count: int = 1
    reactor_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ChannelAction:
    """One outbound channel action."""

    type: ChannelActionType
    target_message_id: str | None = None
    value: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SenderProfile:
    """Normalized sender identity within one transport instance."""

    platform_id: str
    name: str
    handle: str | None = None
    is_bot: bool = False
    canonical_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class GroupProfile:
    """Optional normalized group metadata."""

    group_id: str
    platform_id: str | None = None
    name: str | None = None
    handle: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class UniversalMessage:
    """Normalized inbound message passed to handlers and extensions."""

    id: str
    channel_message_id: str
    instance_id: str
    channel_type: str
    session_id: str
    sender: SenderProfile
    ts: datetime
    thread_id: str | None = None
    group_id: str | None = None
    receiver_id: str | None = None
    bot_mentioned: bool = True
    text: str | None = None
    media: list[MediaRef] = field(default_factory=list)
    interactive: InteractivePayload | None = None
    reply_to_id: str | None = None
    reactions: list[Reaction] = field(default_factory=list)
    edit_of_id: str | None = None
    deleted_id: str | None = None
    group: GroupProfile | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    is_duplicate: bool = False
    envelope_version: str = "1.0"


@dataclass(slots=True)
class OutboundMessage:
    """One outbound intent targeting one destination instance."""

    destination_instance_id: str
    session_id: str
    outbound_id: str
    text: str | None = None
    media: list[MediaRef] = field(default_factory=list)
    interactive: InteractivePayload | None = None
    reply_to_id: str | None = None
    actions: list[ChannelAction] = field(default_factory=list)
    thread_id: str | None = None
    group_id: str | None = None
    stream_id: str | None = None
    is_final: bool = True
    fan_out_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
