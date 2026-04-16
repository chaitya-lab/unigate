"""Rule matcher - evaluates if a message matches a rule."""

from __future__ import annotations

import fnmatch
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..message import Message


class RuleMatcher:
    """Matches messages against rule conditions using plugin matchers."""
    
    _matcher_registry: Any = None
    
    @classmethod
    def _get_registry(cls):
        """Get matcher registry (lazy load)."""
        if cls._matcher_registry is None:
            from .matchers import get_matcher_registry
            cls._matcher_registry = get_matcher_registry()
        return cls._matcher_registry
    
    @classmethod
    def get_matcher(cls, name: str):
        """Get a matcher instance by name."""
        registry = cls._get_registry()
        return registry.create(name)
    
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
        
        Uses matcher registry for extensible matching.
        Falls back to hardcoded matching for backward compatibility.
        
        Returns True if ALL conditions match (AND logic).
        Returns True if condition is None (matches everything).
        """
        from .rule import MatchCondition
        
        if isinstance(condition, type(None)):
            return True
        
        if not hasattr(condition, "from_channel"):
            condition = MatchCondition.from_dict(condition) if condition else MatchCondition()
        
        if condition.matches_everything():
            return True
        
        conditions = condition.to_dict()
        
        for key, value in conditions.items():
            if value is None:
                continue
            
            matcher = cls.get_matcher(key)
            if matcher:
                if not matcher.match(message, value):
                    return False
            else:
                if not cls._match_fallback(key, message, value):
                    return False
        
        return True
    
    @classmethod
    def _match_fallback(cls, key: str, message: "Message", value: Any) -> bool:
        """Fallback matching for keys without plugins."""
        if key == "from_channel":
            return cls.match_channel(message, value)
        elif key == "sender_pattern":
            sender = getattr(message, "sender", None)
            sender_id = getattr(sender, "platform_id", None) if sender else None
            return cls.match_glob(sender_id, value)
        elif key == "text_contains":
            return cls.match_contains(getattr(message, "text", None), value)
        elif key == "text_pattern":
            return cls.match_regex(getattr(message, "text", None), value)
        elif key == "subject_contains":
            metadata = getattr(message, "metadata", {}) or {}
            return cls.match_contains(metadata.get("subject", ""), value)
        elif key == "group_id_pattern":
            return cls.match_glob(getattr(message, "group_id", None), value)
        elif key == "has_media":
            media = getattr(message, "media", None) or []
            return (len(media) > 0) == value
        elif key in ("sender_id", "sender_name_contains", "group_id", "thread_id", "from_instance"):
            return getattr(message, key, None) == value or getattr(getattr(message, "sender", None), key, None) == value
        return True
