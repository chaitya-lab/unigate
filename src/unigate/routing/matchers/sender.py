"""Sender-based routing matcher."""

from __future__ import annotations

import fnmatch
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ....message import Message

from .base import RoutingMatcher


class SenderMatcher(RoutingMatcher):
    """Match based on sender ID or pattern."""

    name = "sender_id"

    def match(self, msg: Message, value: str | list[str]) -> bool:
        if isinstance(value, list):
            return msg.sender.platform_id in value
        return msg.sender.platform_id == value


class SenderPatternMatcher(RoutingMatcher):
    """Match based on sender ID pattern (glob)."""

    name = "sender_pattern"

    def match(self, msg: Message, value: str) -> bool:
        return fnmatch.fnmatch(msg.sender.platform_id, value)


class SenderNameMatcher(RoutingMatcher):
    """Match based on sender name contains."""

    name = "sender_name_contains"

    def match(self, msg: Message, value: str | list[str]) -> bool:
        if isinstance(value, list):
            return any(v.lower() in msg.sender.name.lower() for v in value)
        return value.lower() in msg.sender.name.lower()


class SenderDomainMatcher(RoutingMatcher):
    """Match based on sender email domain."""

    name = "sender_domain"

    def match(self, msg: Message, value: str | list[str]) -> bool:
        if not msg.sender.handle:
            return False
        if "@" not in msg.sender.handle:
            return False

        domain = msg.sender.handle.split("@")[1].lower()
        values = [v.lower() for v in (value if isinstance(value, list) else [value])]
        return domain in values
