"""Text-based routing matcher."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ....message import Message

from .base import RoutingMatcher


class TextContainsMatcher(RoutingMatcher):
    """Match if message text contains substring."""

    name = "text_contains"

    def match(self, msg: Message, value: str | list[str]) -> bool:
        if not msg.text:
            return False
        text_lower = msg.text.lower()
        if isinstance(value, list):
            return any(v.lower() in text_lower for v in value)
        return value.lower() in text_lower


class TextPatternMatcher(RoutingMatcher):
    """Match if message text matches regex pattern."""

    name = "text_pattern"

    def match(self, msg: Message, value: str) -> bool:
        if not msg.text:
            return False
        try:
            return bool(re.search(value, msg.text, re.IGNORECASE))
        except re.error:
            return False


class TextStartsWithMatcher(RoutingMatcher):
    """Match if message text starts with prefix."""

    name = "text_starts_with"

    def match(self, msg: Message, value: str | list[str]) -> bool:
        if not msg.text:
            return False
        if isinstance(value, list):
            return any(msg.text.startswith(v) for v in value)
        return msg.text.startswith(value)


class TextCommandMatcher(RoutingMatcher):
    """Match if message text is a command (starts with /)."""

    name = "is_command"

    def match(self, msg: Message, value: bool = True) -> bool:
        if not msg.text:
            return False
        return msg.text.startswith("/") == value
