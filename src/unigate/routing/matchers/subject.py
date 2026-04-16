"""Subject-based routing matcher (for email-style messages)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ....message import Message

from .base import RoutingMatcher


class SubjectContainsMatcher(RoutingMatcher):
    """Match if message subject contains substring."""

    name = "subject_contains"

    def match(self, msg: Message, value: str | list[str]) -> bool:
        subject = msg.metadata.get("subject", "")
        if not subject:
            return False
        subject_lower = subject.lower()
        if isinstance(value, list):
            return any(v.lower() in subject_lower for v in value)
        return value.lower() in subject_lower


class SubjectPatternMatcher(RoutingMatcher):
    """Match if message subject matches pattern."""

    name = "subject_pattern"

    def match(self, msg: Message, value: str) -> bool:
        import re

        subject = msg.metadata.get("subject", "")
        if not subject:
            return False
        try:
            return bool(re.search(value, subject, re.IGNORECASE))
        except re.error:
            return False


class HasSubjectMatcher(RoutingMatcher):
    """Match if message has a subject."""

    name = "has_subject"

    def match(self, msg: Message, value: bool = True) -> bool:
        subject = msg.metadata.get("subject", "")
        has_subject = bool(subject and subject.strip())
        return has_subject == value
