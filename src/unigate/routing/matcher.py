"""Rule matcher - evaluates if a message matches a rule."""

from __future__ import annotations

import fnmatch
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..message import Message


class RuleMatcher:
    """Matches messages against rule conditions."""
    
    @staticmethod
    def match_channel(message: "Message", pattern: str | None) -> bool:
        """Match message from a specific channel."""
        if not pattern:
            return True
        return getattr(message, "from_instance", None) == pattern
    
    @staticmethod
    def match_glob(value: str | None, pattern: str | None) -> bool:
        """Match using glob pattern (supports * wildcard)."""
        if not pattern:
            return True
        if not value:
            return False
        return fnmatch.fnmatch(value, pattern)
    
    @staticmethod
    def match_regex(value: str | None, pattern: str | None) -> bool:
        """Match using regex pattern."""
        if not pattern:
            return True
        if not value:
            return False
        try:
            return bool(re.search(pattern, value))
        except re.error:
            return False
    
    @staticmethod
    def match_contains(value: str | None, substring: str | None, case_sensitive: bool = False) -> bool:
        """Match if value contains substring."""
        if not substring:
            return True
        if not value:
            return False
        if case_sensitive:
            return substring in value
        return substring.lower() in value.lower()
    
    @classmethod
    def match_message(cls, message: "Message", condition: "MatchCondition") -> bool:
        """
        Check if a message matches all conditions in the given condition object.
        
        Returns True if ALL conditions match (AND logic).
        Returns True if condition is None (matches everything).
        """
        from .rule import MatchCondition
        
        if isinstance(condition, type(None)):
            return True
        
        if not hasattr(condition, "from_channel"):
            condition = MatchCondition.from_dict(condition) if condition else MatchCondition()
        
        # Empty condition matches everything
        if condition.matches_everything():
            return True
        
        # from_channel
        if condition.from_channel:
            if not cls.match_channel(message, condition.from_channel):
                return False
        
        # from_instance
        if condition.from_instance:
            if getattr(message, "from_instance", None) != condition.from_instance:
                return False
        
        # sender_id
        if condition.sender_id:
            sender = getattr(message, "sender", None)
            sender_id = getattr(sender, "platform_id", None) if sender else None
            if sender_id != condition.sender_id:
                return False
        
        # sender_pattern (glob)
        if condition.sender_pattern:
            sender = getattr(message, "sender", None)
            sender_id = getattr(sender, "platform_id", None) if sender else None
            if not cls.match_glob(sender_id, condition.sender_pattern):
                return False
        
        # sender_name_contains
        if condition.sender_name_contains:
            sender = getattr(message, "sender", None)
            sender_name = getattr(sender, "name", None) if sender else None
            if not cls.match_contains(sender_name, condition.sender_name_contains):
                return False
        
        # text_contains
        if condition.text_contains:
            text = getattr(message, "text", None)
            if not cls.match_contains(text, condition.text_contains):
                return False
        
        # text_pattern (regex)
        if condition.text_pattern:
            text = getattr(message, "text", None)
            if not cls.match_regex(text, condition.text_pattern):
                return False
        
        # subject_contains (email)
        if condition.subject_contains:
            metadata = getattr(message, "metadata", {}) or {}
            subject = metadata.get("subject", "")
            if not cls.match_contains(subject, condition.subject_contains):
                return False
        
        # group_id
        if condition.group_id:
            if getattr(message, "group_id", None) != condition.group_id:
                return False
        
        # group_id_pattern (glob)
        if condition.group_id_pattern:
            group_id = getattr(message, "group_id", None)
            if not cls.match_glob(group_id, condition.group_id_pattern):
                return False
        
        # thread_id
        if condition.thread_id:
            if getattr(message, "thread_id", None) != condition.thread_id:
                return False
        
        # has_media
        if condition.has_media is not None:
            media = getattr(message, "media", None) or []
            has_media = len(media) > 0
            if has_media != condition.has_media:
                return False
        
        return True
