"""Routing rule definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MatchCondition:
    """Conditions for matching a message."""
    
    from_channel: str | None = None
    from_instance: str | None = None
    sender_pattern: str | None = None
    sender_id: str | None = None
    sender_name_contains: str | None = None
    text_contains: str | None = None
    text_pattern: str | None = None
    subject_contains: str | None = None
    group_id_pattern: str | None = None
    group_id: str | None = None
    thread_id: str | None = None
    has_media: bool | None = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> MatchCondition | None:
        if not data:
            return None
        return cls(
            from_channel=data.get("from_channel"),
            from_instance=data.get("from_instance"),
            sender_pattern=data.get("sender_pattern"),
            sender_id=data.get("sender_id"),
            sender_name_contains=data.get("sender_name_contains"),
            text_contains=data.get("text_contains"),
            text_pattern=data.get("text_pattern"),
            subject_contains=data.get("subject_contains"),
            group_id_pattern=data.get("group_id_pattern"),
            group_id=data.get("group_id"),
            thread_id=data.get("thread_id"),
            has_media=data.get("has_media"),
        )
    
    def matches_everything(self) -> bool:
        """Return True if this condition matches everything."""
        return all(
            getattr(self, attr) is None 
            for attr in [
                "from_channel", "from_instance", "sender_pattern", "sender_id",
                "sender_name_contains", "text_contains", "text_pattern",
                "subject_contains", "group_id_pattern", "group_id",
                "thread_id", "has_media"
            ]
        )


@dataclass
class RoutingAction:
    """Actions to take when a rule matches."""
    
    forward_to: list[str] = field(default_factory=list)
    extensions: list[str] = field(default_factory=list)
    keep_in_default: bool = False
    add_tags: list[str] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> RoutingAction | None:
        if not data:
            return None
        return cls(
            forward_to=data.get("forward_to", []),
            extensions=data.get("extensions", []),
            keep_in_default=data.get("keep_in_default", False),
            add_tags=data.get("add_tags", []),
        )


@dataclass
class RoutingRule:
    """
    A single routing rule.
    
    Rules are evaluated in priority order (lower = higher priority).
    First matching rule wins.
    """
    
    name: str
    priority: int = 100
    enabled: bool = True
    match: MatchCondition | None = None
    actions: RoutingAction | None = None
    
    def __post_init__(self) -> None:
        if self.match is None:
            self.match = MatchCondition()
        if self.actions is None:
            self.actions = RoutingAction()
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoutingRule:
        """Create a rule from a dictionary."""
        match_data = data.get("match", {})
        if match_data == {}:
            match_data = None
        
        action_data = data.get("actions", {})
        if action_data == {}:
            action_data = None
            
        return cls(
            name=data.get("name", "unnamed"),
            priority=data.get("priority", 100),
            enabled=data.get("enabled", True),
            match=MatchCondition.from_dict(match_data),
            actions=RoutingAction.from_dict(action_data),
        )
    
    def matches(self, message: Any) -> bool:
        """Check if this rule matches the given message."""
        if not self.enabled:
            return False
        
        if self.match is None or self.match.matches_everything():
            return True
        
        # Use the matcher for consistency
        from .matcher import RuleMatcher
        return RuleMatcher.match_message(message, self.match)
    
    # Alias for engine compatibility
    def match_message(self, message: Any) -> bool:
        """Alias for matches()."""
        return self.matches(message)


def load_rules_from_config(config: dict[str, Any]) -> list[RoutingRule]:
    """Load routing rules from config dict."""
    rules = []
    
    # Get rules from config
    routing_config = config.get("routing", {})
    if isinstance(routing_config, dict):
        rules_data = routing_config.get("rules", [])
    elif isinstance(routing_config, list):
        rules_data = routing_config
    else:
        rules_data = []
    
    for rule_data in rules_data:
        if isinstance(rule_data, dict):
            rule = RoutingRule.from_dict(rule_data)
            rules.append(rule)
    
    # Sort by priority
    rules.sort(key=lambda r: r.priority)
    
    return rules
