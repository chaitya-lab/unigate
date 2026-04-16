"""Web channel plugin."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..message import Message


class WebChannelPlugin:
    """Generic HTTP webhook channel."""
    
    name = "web"
    type = "channel"
    
    async def receive(self, raw: dict[str, Any]) -> Message | None:
        """Convert webhook payload to Message."""
        from ..message import Message, Sender
        from datetime import datetime, timezone
        
        sender_data = raw.get("sender", {})
        sender = Sender(
            platform_id=str(sender_data.get("id", "anonymous")),
            name=str(sender_data.get("name", "Anonymous")),
            handle=sender_data.get("handle"),
        )
        
        return Message(
            id=raw.get("id", str(id(raw))),
            session_id=raw.get("session_id", sender.platform_id),
            from_instance=self.name,
            sender=sender,
            ts=datetime.now(timezone.utc),
            text=raw.get("text"),
            group_id=raw.get("group_id"),
            thread_id=raw.get("thread_id"),
            media=raw.get("media", []),
            raw=raw,
        )
    
    async def send(self, msg: Message) -> dict[str, Any] | None:
        """Convert Message to webhook format."""
        return {
            "id": msg.id,
            "text": msg.text,
            "sender": {
                "id": msg.sender.platform_id,
                "name": msg.sender.name,
            },
        }
