"""Media matcher plugins."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..message import Message


class HasMediaMatcher:
    """Match if message has media attachments."""
    
    name = "has_media"
    type = "match"
    
    def match(self, msg: Message, value: bool = True) -> bool:
        has_media = len(msg.media) > 0
        return has_media == value


class HasAttachmentMatcher:
    """Match if message has file attachments."""
    
    name = "has_attachment"
    type = "match"
    
    def match(self, msg: Message, value: bool = True) -> bool:
        has_attachment = any(m.type.value in ("file", "document") for m in msg.media)
        return has_attachment == value


class HasImageMatcher:
    """Match if message has image attachments."""
    
    name = "has_image"
    type = "match"
    
    def match(self, msg: Message, value: bool = True) -> bool:
        has_image = any(m.type.value == "image" for m in msg.media)
        return has_image == value


class HasVideoMatcher:
    """Match if message has video attachments."""
    
    name = "has_video"
    type = "match"
    
    def match(self, msg: Message, value: bool = True) -> bool:
        has_video = any(m.type.value == "video" for m in msg.media)
        return has_video == value


class MediaTypeMatcher:
    """Match by media type."""
    
    name = "media_type"
    type = "match"
    
    def match(self, msg: Message, value: str | list[str]) -> bool:
        if not msg.media:
            return False
        media_types = {m.type.value for m in msg.media}
        if isinstance(value, list):
            return bool(media_types & set(value))
        return value in media_types
