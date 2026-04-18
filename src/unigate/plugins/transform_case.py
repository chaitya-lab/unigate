"""Case transform plugins."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..message import Message


class UppercaseTransform:
    """Convert message text to uppercase."""
    
    name = "uppercase"
    type = "transform"
    
    async def transform(self, msg: Message, config: dict[str, Any]) -> Message:
        if msg.text:
            msg.text = msg.text.upper()
        return msg


class LowercaseTransform:
    """Convert message text to lowercase."""
    
    name = "lowercase"
    type = "transform"
    
    async def transform(self, msg: Message, config: dict[str, Any]) -> Message:
        if msg.text:
            msg.text = msg.text.lower()
        return msg


class TitleCaseTransform:
    """Convert message text to title case."""
    
    name = "titlecase"
    type = "transform"
    
    async def transform(self, msg: Message, config: dict[str, Any]) -> Message:
        if msg.text:
            msg.text = msg.text.title()
        return msg