"""Sender matcher plugins."""

from __future__ import annotations

import fnmatch
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..message import Message


class SenderMatcher:
    """Match by sender ID."""
    
    name = "sender"
    type = "match"
    
    def match(self, msg: Message, value: str | list[str]) -> bool:
        if isinstance(value, list):
            return msg.sender.platform_id in value
        return msg.sender.platform_id == value


class SenderPatternMatcher:
    """Match by sender ID pattern (glob)."""
    
    name = "sender_pattern"
    type = "match"
    
    def match(self, msg: Message, value: str) -> bool:
        return fnmatch.fnmatch(msg.sender.platform_id, value)


class SenderNameMatcher:
    """Match by sender name contains."""
    
    name = "sender_name"
    type = "match"
    
    def match(self, msg: Message, value: str | list[str]) -> bool:
        if isinstance(value, list):
            return any(v.lower() in msg.sender.name.lower() for v in value)
        return value.lower() in msg.sender.name.lower()


class SenderDomainMatcher:
    """Match by sender email domain."""
    
    name = "sender_domain"
    type = "match"
    
    def match(self, msg: Message, value: str | list[str]) -> bool:
        if not msg.sender.handle or "@" not in msg.sender.handle:
            return False
        domain = msg.sender.handle.split("@")[1].lower()
        values = [v.lower() for v in (value if isinstance(value, list) else [value])]
        return domain in values
