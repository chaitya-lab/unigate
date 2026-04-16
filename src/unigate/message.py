"""Universal message contracts for the 1.5 architecture."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


@dataclass(slots=True)
class Sender:
    """Normalized sender identity."""

    platform_id: str
    name: str
    handle: str | None = None
    is_bot: bool = False
    canonical_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class MediaType(str, Enum):
    """Universal media categories."""

    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    VOICE = "voice"
    FILE = "file"
    STICKER = "sticker"
    LOCATION = "location"
    CONTACT = "contact"


@dataclass(slots=True)
class MediaRef:
    """Lazy media reference."""

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
    _data: bytes | None = None

    async def resolve(self) -> bytes:
        """Fetch media bytes on demand."""
        if self._data is not None:
            return self._data
        if self.full_url is None:
            raise ValueError(f"No URL to resolve for media {self.media_id}")
        import urllib.request
        with urllib.request.urlopen(self.full_url) as resp:
            self._data = resp.read()
        return self._data

    async def resolve_url(self) -> str:
        """Return or resolve the full URL for this media."""
        if self.full_url:
            return self.full_url
        if self.thumbnail_url:
            return self.thumbnail_url
        raise ValueError(f"No URL available for media {self.media_id}")


class InteractionType:
    """Built-in interaction type constants."""

    CONFIRM = "confirm"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    TEXT_INPUT = "text_input"
    PASSWORD = "password"
    NUMBER = "number"
    FILE_UPLOAD = "file_upload"
    OTP = "otp"
    FORM = "form"


@dataclass(slots=True)
class FormField:
    """Structured form field."""

    name: str
    label: str
    type: str
    required: bool = True
    options: list[str] | None = None


@dataclass(slots=True)
class InteractiveResponse:
    """Normalized interactive response."""

    interaction_id: str
    type: str
    value: str | list[str] | dict[str, Any] | None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Interactive:
    """Universal interactive payload."""

    interaction_id: str
    type: str
    prompt: str
    options: list[str] | None = None
    fields: list[FormField] | None = None
    min_value: float | None = None
    max_value: float | None = None
    timeout_seconds: int | None = None
    context: dict[str, Any] = field(default_factory=dict)
    response: InteractiveResponse | None = None


@dataclass(slots=True)
class Action:
    """Universal side-effect action."""

    type: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Reaction:
    """Reaction on a message."""

    emoji: str
    sender_id: str
    ts: datetime


@dataclass(slots=True)
class Message:
    """Universal message used in both directions."""

    id: str
    session_id: str
    from_instance: str
    sender: Sender
    ts: datetime
    platform_id: str | None = None
    to: list[str] = field(default_factory=list)
    thread_id: str | None = None
    group_id: str | None = None
    receiver_id: str | None = None
    bot_mentioned: bool = True
    text: str | None = None
    media: list[MediaRef] = field(default_factory=list)
    interactive: Interactive | None = None
    actions: list[Action] = field(default_factory=list)
    reply_to_id: str | None = None
    reactions: list[Reaction] = field(default_factory=list)
    edit_of_id: str | None = None
    deleted_id: str | None = None
    stream_id: str | None = None
    is_final: bool = True
    raw: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
