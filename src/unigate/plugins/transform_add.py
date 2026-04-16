"""Add metadata transform plugins."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..message import Message


class AddMetadataTransform:
    """Add static metadata to message."""
    
    name = "add_metadata"
    type = "transform"
    
    async def transform(self, msg: Message, config: dict[str, Any]) -> Message:
        for key, value in config.get("metadata", {}).items():
            msg.metadata[key] = value
        return msg


class AddTimestampTransform:
    """Add current timestamp to metadata."""
    
    name = "add_timestamp"
    type = "transform"
    
    async def transform(self, msg: Message, config: dict[str, Any]) -> Message:
        key = config.get("key", "routed_at")
        format_str = config.get("format", "iso")
        
        if format_str == "iso":
            msg.metadata[key] = datetime.now(timezone.utc).isoformat()
        elif format_str == "unix":
            msg.metadata[key] = int(datetime.now(timezone.utc).timestamp())
        else:
            msg.metadata[key] = datetime.now(timezone.utc).isoformat()
        
        return msg


class AddPrefixTransform:
    """Add prefix to message text."""
    
    name = "add_prefix"
    type = "transform"
    
    async def transform(self, msg: Message, config: dict[str, Any]) -> Message:
        prefix = config.get("prefix", "")
        if msg.text and prefix:
            msg.text = f"{prefix}{msg.text}"
        return msg


class AddSenderTransform:
    """Add sender info to message."""
    
    name = "add_sender"
    type = "transform"
    
    async def transform(self, msg: Message, config: dict[str, Any]) -> Message:
        where = config.get("where", "metadata")
        format_str = config.get("format", "[{name}]")
        
        sender_text = format_str.format(
            name=msg.sender.name,
            handle=msg.sender.handle or "",
            id=msg.sender.platform_id,
        )
        
        if where == "text":
            if msg.text:
                msg.text = f"{sender_text} {msg.text}"
            else:
                msg.text = sender_text
        else:
            msg.metadata["sender_text"] = sender_text
        
        return msg


class AddTagTransform:
    """Add tag to message metadata."""
    
    name = "add_tag"
    type = "transform"
    
    async def transform(self, msg: Message, config: dict[str, Any]) -> Message:
        tags = config.get("tags", [])
        if not isinstance(tags, list):
            tags = [tags]
        
        if "tags" not in msg.metadata:
            msg.metadata["tags"] = []
        
        msg.metadata["tags"].extend(tags)
        return msg
