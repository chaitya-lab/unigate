"""Context-based routing matcher (group, thread, session)."""

from __future__ import annotations

import fnmatch
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ....message import Message

from .base import RoutingMatcher


class GroupMatcher(RoutingMatcher):
    """Match based on group ID."""

    name = "group_id"

    def match(self, msg: Message, value: str | list[str]) -> bool:
        if not msg.group_id:
            return False
        if isinstance(value, list):
            return msg.group_id in value
        return msg.group_id == value


class GroupPatternMatcher(RoutingMatcher):
    """Match based on group ID pattern (glob)."""

    name = "group_id_pattern"

    def match(self, msg: Message, value: str) -> bool:
        if not msg.group_id:
            return False
        return fnmatch.fnmatch(msg.group_id, value)


class ThreadMatcher(RoutingMatcher):
    """Match based on thread ID."""

    name = "thread_id"

    def match(self, msg: Message, value: str | list[str]) -> bool:
        if not msg.thread_id:
            return False
        if isinstance(value, list):
            return msg.thread_id in value
        return msg.thread_id == value


class SessionMatcher(RoutingMatcher):
    """Match based on session ID."""

    name = "session_id"

    def match(self, msg: Message, value: str | list[str]) -> bool:
        if isinstance(value, list):
            return msg.session_id in value
        return msg.session_id == value


class BotMentionedMatcher(RoutingMatcher):
    """Match based on whether bot was mentioned."""

    name = "bot_mentioned"

    def match(self, msg: Message, value: bool = True) -> bool:
        return msg.bot_mentioned == value
