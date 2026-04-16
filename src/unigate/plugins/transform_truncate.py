"""Truncate transform plugin."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..message import Message


class TruncateTransform:
    """Truncate message text to max length."""
    
    name = "truncate"
    type = "transform"
    
    async def transform(self, msg: Message, config: dict[str, Any]) -> Message:
        max_length = config.get("max_length", 160)
        suffix = config.get("suffix", "...")
        
        if msg.text and len(msg.text) > max_length:
            msg.text = msg.text[:max_length - len(suffix)] + suffix
        
        return msg


class Truncate160Transform:
    """Truncate to 160 chars (SMS style)."""
    
    name = "truncate_160"
    type = "transform"
    
    async def transform(self, msg: Message, config: dict[str, Any]) -> Message:
        max_length = 160
        suffix = "..."
        
        if msg.text and len(msg.text) > max_length:
            msg.text = msg.text[:max_length - len(suffix)] + suffix
        
        return msg
