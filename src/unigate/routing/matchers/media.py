"""Media-based routing matcher."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ....message import Message

from .base import RoutingMatcher


class HasMediaMatcher(RoutingMatcher):
    """Match if message has media attachments."""

    name = "has_media"

    def match(self, msg: Message, value: bool = True) -> bool:
        has_media = len(msg.media) > 0
        return has_media == value


class HasAttachmentMatcher(RoutingMatcher):
    """Match if message has file attachments (non-image/video/audio)."""

    name = "has_attachment"

    def match(self, msg: Message, value: bool = True) -> bool:
        has_attachment = any(
            m.type.value in ("file", "document") for m in msg.media
        )
        return has_attachment == value


class MediaTypeMatcher(RoutingMatcher):
    """Match based on media type."""

    name = "media_type"

    def match(self, msg: Message, value: str | list[str]) -> bool:
        if not msg.media:
            return False
        media_types = {m.type.value for m in msg.media}
        if isinstance(value, list):
            return bool(media_types & set(value))
        return value in media_types


class HasImageMatcher(RoutingMatcher):
    """Match if message has image attachments."""

    name = "has_image"

    def match(self, msg: Message, value: bool = True) -> bool:
        has_image = any(m.type.value == "image" for m in msg.media)
        return has_image == value


class HasVideoMatcher(RoutingMatcher):
    """Match if message has video attachments."""

    name = "has_video"

    def match(self, msg: Message, value: bool = True) -> bool:
        has_video = any(m.type.value == "video" for m in msg.media)
        return has_video == value
