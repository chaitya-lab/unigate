"""From matcher plugin - match by source channel."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..message import Message


class FromMatcher:
    """Match message by source channel/instance."""
    
    name = "from"
    type = "match"
    
    def match(self, msg: Message, value: str | list[str]) -> bool:
        if isinstance(value, list):
            return msg.from_instance in value
        return msg.from_instance == value


class FromPatternMatcher:
    """Match message by source pattern (glob)."""
    
    name = "from_pattern"
    type = "match"
    
    def match(self, msg: Message, value: str) -> bool:
        import fnmatch
        return fnmatch.fnmatch(msg.from_instance, value)
