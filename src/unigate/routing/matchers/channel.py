"""Channel-based routing matcher."""

from __future__ import annotations

import fnmatch
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ....message import Message

from .base import RoutingMatcher


class ChannelMatcher(RoutingMatcher):
    """Match based on source channel."""

    name = "from_channel"

    def match(self, msg: Message, value: str | list[str]) -> bool:
        if isinstance(value, list):
            return msg.from_instance in value
        return msg.from_instance == value


class ChannelPatternMatcher(RoutingMatcher):
    """Match based on channel pattern (glob)."""

    name = "from_channel_pattern"

    def match(self, msg: Message, value: str) -> bool:
        return fnmatch.fnmatch(msg.from_instance, value)
