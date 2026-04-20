"""Text matcher plugins."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..message import Message


class TextContainsMatcher:
    """Match if message text contains substring."""
    
    name = "text_contains"
    type = "match"
    parameters = {
        "value": {"type": "str|list", "description": "Text or list of texts to match"},
    }
    
    def match(self, msg: Message, value: str | list[str]) -> bool:
        if not msg.text:
            return False
        text_lower = msg.text.lower()
        if isinstance(value, list):
            return any(v.lower() in text_lower for v in value)
        return value.lower() in text_lower


class TextPatternMatcher:
    """Match if message text matches regex pattern."""
    
    name = "text_pattern"
    type = "match"
    parameters = {
        "value": {"type": "str", "description": "Regex pattern"},
    }
    
    def match(self, msg: Message, value: str) -> bool:
        if not msg.text:
            return False
        try:
            return bool(re.search(value, msg.text, re.IGNORECASE))
        except re.error:
            return False


class TextStartsWithMatcher:
    """Match if message text starts with prefix."""
    
    name = "text_starts"
    type = "match"
    parameters = {
        "value": {"type": "str|list", "description": "Prefix or list of prefixes"},
    }
    
    def match(self, msg: Message, value: str | list[str]) -> bool:
        if not msg.text:
            return False
        if isinstance(value, list):
            return any(msg.text.startswith(v) for v in value)
        return msg.text.startswith(value)


class IsCommandMatcher:
    """Match if message is a command (starts with /)."""
    
    name = "is_command"
    type = "match"
    parameters = {
        "value": {"type": "bool", "description": "True=is command, False=not command", "default": True},
    }
    
    def match(self, msg: Message, value: bool = True) -> bool:
        if not msg.text:
            return False
        return msg.text.startswith("/") == value


class SubjectContainsMatcher:
    """Match if message subject contains substring."""
    
    name = "subject_contains"
    type = "match"
    parameters = {
        "value": {"type": "str|list", "description": "Text or list to match in subject"},
    }
    
    def match(self, msg: Message, value: str | list[str]) -> bool:
        subject = msg.metadata.get("subject", "")
        if not subject:
            return False
        subject_lower = subject.lower()
        if isinstance(value, list):
            return any(v.lower() in subject_lower for v in value)
        return value.lower() in subject_lower
