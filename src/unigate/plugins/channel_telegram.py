"""Telegram channel plugin."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..message import Message


class TelegramChannelPlugin:
    """Telegram Bot API channel."""
    
    name = "telegram"
    type = "channel"
    
    async def receive(self, raw: dict[str, Any]) -> Message | None:
        """Convert Telegram update to Message."""
        from ..message import Message, Sender
        from datetime import datetime, timezone
        
        update = raw.get("update", raw)
        message = update.get("message", update)
        
        if not message:
            return None
        
        from_user = message.get("from", {})
        chat = message.get("chat", {})
        
        sender = Sender(
            platform_id=str(from_user.get("id", "")),
            name=from_user.get("first_name", "User"),
            handle=from_user.get("username"),
            is_bot=from_user.get("is_bot", False),
        )
        
        text = message.get("text") or message.get("caption", "")
        
        return Message(
            id=str(message.get("message_id", "")),
            session_id=str(chat.get("id", "")),
            from_instance=self.name,
            sender=sender,
            ts=datetime.now(timezone.utc),
            text=text,
            group_id=str(chat.get("id")) if chat.get("type") != "private" else None,
            raw=message,
            metadata={
                "chat_type": chat.get("type"),
                "chat_title": chat.get("title"),
            },
        )
    
    async def send(self, msg: Message) -> dict[str, Any] | None:
        """Convert Message to Telegram format."""
        return {
            "text": msg.text,
        }
