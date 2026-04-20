"""Routing system - evaluates rules and routes messages."""

from __future__ import annotations

import asyncio
import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .message import Message
from .plugins.base import get_registry

if TYPE_CHECKING:
    from .kernel import Exchange


@dataclass
class MatchCondition:
    """Conditions for matching a message.
    
    Supports three syntaxes:
    
    1. Simple (current):
       match:
         from_instance: web
         sender_id: "123"
         text_contains: "hello"
    
    2. Type-based (new):
       match:
         - type: sender_id
           op: eq
           value: "123"
         - type: text
           op: contains
           value: "urgent"
         - type: sender_id
           op: in
           value: ["123", "456", "789"]
    
    3. Code (new):
       match:
         code: "msg.sender.platform_id == '123' or 'urgent' in (msg.text or '')"
    """
    
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
    has_attachment: bool | None = None
    has_image: bool | None = None
    has_video: bool | None = None
    media_type: str | None = None
    day_of_week: str | list[str] | None = None
    hour_of_day: int | list[int] | str | None = None
    
    # New: code-based and type-based matching
    code: str | None = None
    conditions: list[dict] | None = None  # [{"type": "field", "op": "op", "value": ...}]
    
    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> MatchCondition | None:
        if not data:
            return None
        
        # Handle type-based match: list of conditions directly
        if isinstance(data, list):
            return cls(
                conditions=data,
            )
        
        # Handle dict - extract code and conditions
        conditions = None
        if isinstance(data, dict):
            conditions = data.get("conditions")
            code = data.get("code")
        
        # Handle simple keys
        
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
            has_attachment=data.get("has_attachment"),
            has_image=data.get("has_image"),
            has_video=data.get("has_video"),
            media_type=data.get("media_type"),
            day_of_week=data.get("day_of_week"),
            hour_of_day=data.get("hour_of_day"),
            code=data.get("code"),
            conditions=conditions,
        )
    
    def to_dict(self) -> dict[str, Any]:
        result = {
            "from_channel": self.from_channel,
            "from_instance": self.from_instance,
            "sender_pattern": self.sender_pattern,
            "sender_id": self.sender_id,
            "sender_name_contains": self.sender_name_contains,
            "text_contains": self.text_contains,
            "text_pattern": self.text_pattern,
            "subject_contains": self.subject_contains,
            "group_id_pattern": self.group_id_pattern,
            "group_id": self.group_id,
            "thread_id": self.thread_id,
            "has_media": self.has_media,
            "has_attachment": self.has_attachment,
            "has_image": self.has_image,
            "has_video": self.has_video,
            "media_type": self.media_type,
            "day_of_week": self.day_of_week,
            "hour_of_day": self.hour_of_day,
        }
        if self.code:
            result["code"] = self.code
        if self.conditions:
            result["conditions"] = self.conditions
        return result
    
    def matches_everything(self) -> bool:
        # Check simple matches AND code/conditions
        simple = any(v is not None for v in self.to_dict().values() if v is not None)
        has_code = bool(self.code)
        has_conditions = bool(self.conditions and len(self.conditions) > 0)
        return not (simple or has_code or has_conditions)


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
    """A single routing rule. First matching rule wins."""
    
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
    
    def match_message(self, message: Message) -> bool:
        if not self.enabled:
            return False
        if self.match is None:
            return True
        
        # Handle code-based matching ONLY
        if self.match.code:
            return RuleMatcher.match_code(message, self.match.code)
        
        # Handle type-based conditions ONLY
        if self.match.conditions:
            return RuleMatcher.match_conditions(message, self.match.conditions)
        
        # Original simple matching
        if self.match.matches_everything():
            return True
        return RuleMatcher.match_message(message, self.match)


class RuleMatcher:
    """Matches messages against rule conditions."""
    
    _plugin_registry: Any = None
    
    @classmethod
    def _get_registry(cls):
        if cls._plugin_registry is None:
            cls._plugin_registry = get_registry()
        return cls._plugin_registry
    
    @classmethod
    def get_matcher(cls, name: str):
        registry = cls._get_registry()
        return registry.create_match(name)
    
    @staticmethod
    def match_channel(message: Message, pattern: str | None) -> bool:
        if not pattern:
            return True
        return getattr(message, "from_instance", None) == pattern
    
    @staticmethod
    def match_glob(value: str | None, pattern: str | None) -> bool:
        if not pattern:
            return True
        if not value:
            return False
        return fnmatch.fnmatch(value, pattern)
    
    @staticmethod
    def match_regex(value: str | None, pattern: str | None) -> bool:
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
        if not substring:
            return True
        if not value:
            return False
        if case_sensitive:
            return substring in value
        return substring.lower() in value.lower()
    
    @classmethod
    def match_message(cls, message: Message, condition: MatchCondition) -> bool:
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
    def match_code(cls, message: Message, code: str) -> bool:
        """Match using Python code.
        
        Code has access to:
          - msg: Message object
          - config: dict
        
        Example: "msg.sender.platform_id == '123' or 'urgent' in (msg.text or '')"
        """
        if not code:
            return False
        try:
            context = {"msg": message, "config": {}}
            result = eval(code, {"__builtins__": {}}, context)
            return bool(result) if result is not None else False
        except Exception:
            return False
    
    @classmethod
    def match_conditions(cls, message: Message, conditions: list[dict]) -> bool:
        """Match using type-based conditions.
        
        Format:
          - type: sender_id      # field name
            op: eq           # operation: eq, ne, contains, startswith, endswith, in, gt, lt, regex
            value: "123"     # value to match
          
          # Optional: combine with OR instead of AND
          - type: sender_id
            op: startswith
            value: "vip_"
            logic: or        # makes this OR with previous
        
        Example (AND - default):
          - type: sender_id
            op: in
            value: ["123", "456"]
          - type: text
            op: contains
            value: "urgent"   # both must match
        
        Example (OR):
          - type: sender_id
            op: in
            value: ["123", "456"]
          - type: sender_id
            op: startswith  
            value: "vip_"
            logic: or        # either must match
        """
        if not conditions:
            return True
        
        # Check if any condition has logic: or
        has_or = any(cond.get("logic", "").lower() == "or" for cond in conditions if isinstance(cond, dict))
        
        if has_or:
            # OR logic: return True if ANY matches
            for cond in conditions:
                if not isinstance(cond, dict):
                    continue
                
                field = cond.get("type")
                op = cond.get("op", "eq")
                value = cond.get("value")
                
                if not field:
                    continue
                
                field_value = cls._get_field_value(message, field)
                
                if cls._match_value(field_value, op, value):
                    return True
            
            return False
        else:
            # AND logic: return False if ANY doesn't match
            for cond in conditions:
                if not isinstance(cond, dict):
                    continue
                
                field = cond.get("type")
                op = cond.get("op", "eq")
                value = cond.get("value")
                
                if not field:
                    continue
                
                field_value = cls._get_field_value(message, field)
                
                if not cls._match_value(field_value, op, value):
                    return False
            
            return True
    
    @staticmethod
    def _get_field_value(message: Message, field: str) -> Any:
        """Get field value from message by name.
        
        Supports nested access like sender.id, metadata.key, raw.update_id
        """
        parts = field.split(".")
        value = message
        
        for part in parts:
            if value is None:
                return None
            if hasattr(value, part):
                value = getattr(value, part)
            elif isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        
        return value
    
    @classmethod
    def _match_value(cls, field_value: Any, op: str, match_value: Any) -> bool:
        """Match field value with operation."""
        if op == "eq":
            return field_value == match_value
        elif op == "ne":
            return field_value != match_value
        elif op == "contains":
            return match_value and str(match_value) in str(field_value)
        elif op == "startswith":
            return field_value and str(field_value).startswith(str(match_value))
        elif op == "endswith":
            return field_value and str(field_value).endswith(str(match_value))
        elif op == "in":
            return field_value in match_value if isinstance(match_value, (list, tuple, set)) else field_value == match_value
        elif op == "gt" and field_value is not None and match_value is not None:
            try:
                return float(field_value) > float(match_value)
            except (ValueError, TypeError):
                return False
        elif op == "lt" and field_value is not None and match_value is not None:
            try:
                return float(field_value) < float(match_value)
            except (ValueError, TypeError):
                return False
        elif op == "regex" and field_value and match_value:
            import re
            return re.search(str(match_value), str(field_value)) is not None
        elif op == "exists":
            return (field_value is not None) == match_value
        else:
            return field_value == match_value
    
    @classmethod
    def _match_fallback(cls, key: str, message: Message, value: Any) -> bool:
        if key == "from_channel":
            return cls.match_channel(message, value)
        elif key == "from_instance":
            return getattr(message, "from_instance", None) == value
        elif key == "sender_pattern":
            sender = getattr(message, "sender", None)
            sender_id = getattr(sender, "platform_id", None) if sender else None
            return cls.match_glob(sender_id, value)
        elif key == "sender_id":
            sender = getattr(message, "sender", None)
            sender_id = getattr(sender, "platform_id", None) if sender else None
            return sender_id == value
        elif key == "sender_name_contains":
            sender = getattr(message, "sender", None)
            sender_name = getattr(sender, "name", None) if sender else None
            return cls.match_contains(sender_name, value)
        elif key == "text_contains":
            return cls.match_contains(getattr(message, "text", None), value)
        elif key == "text_pattern":
            return cls.match_regex(getattr(message, "text", None), value)
        elif key == "subject_contains":
            metadata = getattr(message, "metadata", {}) or {}
            return cls.match_contains(metadata.get("subject", ""), value)
        elif key == "group_id_pattern":
            return cls.match_glob(getattr(message, "group_id", None), value)
        elif key == "group_id":
            return cls.match_glob(getattr(message, "group_id", None), value)
        elif key == "thread_id":
            return getattr(message, "thread_id", None) == value
        elif key == "has_media":
            media = getattr(message, "media", None) or []
            return (len(media) > 0) == value
        elif key == "has_attachment":
            media = getattr(message, "media", None) or []
            has_attachment = any(m.type == "file" for m in media) if media else False
            return has_attachment == value
        elif key == "has_image":
            media = getattr(message, "media", None) or []
            has_image = any(m.type == "image" for m in media) if media else False
            return has_image == value
        elif key == "has_video":
            media = getattr(message, "media", None) or []
            has_video = any(m.type == "video" for m in media) if media else False
            return has_video == value
        return True


class RoutingEngine:
    """
    Routes messages based on configurable rules.
    
    Flow:
    1. Message arrives from channel
    2. Find matching rule (priority order)
    3. Run transforms
    4. Forward to destinations
    """

    def __init__(
        self,
        exchange: Exchange,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.exchange = exchange
        self.config = config or {}
        self._rules: list[RoutingRule] = []
        self._extensions: dict[str, Any] = {}
        self._extensions_config: list = config.get("extensions", []) if config else []
        self._plugin_registry = get_registry()
        self._default_action: str = "keep"
        self._default_instance: str | None = "default"
        self._unprocessed_retention_days: int = 7
        self._routing_enabled: bool = True
        self._warnings: list[str] = []
        
        self._load_config(self.config)
        self._load_extensions()

    def _load_config(self, config: dict[str, Any]) -> None:
        routing = config.get("routing", {})
        self._default_action = routing.get("default_action", "keep")
        self._default_instance = routing.get("default_instance")
        unprocessed = routing.get("unprocessed", {})
        self._unprocessed_retention_days = unprocessed.get("retention_days", 7)
        
        strict = routing.get("strict_mode", False)
        self._rules, warnings = load_rules_from_config(config, strict)
        
        for w in warnings:
            self._warnings.append(w)
        
        rules_file = routing.get("rules_file")
        if rules_file:
            self._load_rules_from_file(rules_file)

    def _load_rules_from_file(self, filepath: str) -> None:
        import yaml
        path = Path(filepath)
        if path.exists():
            with open(path) as f:
                data = yaml.safe_load(f)
            if data:
                file_rules = load_rules_from_config(data)
                existing_names = {r.name for r in self._rules}
                for rule in file_rules:
                    if rule.name not in existing_names:
                        self._rules.append(rule)
                self._rules.sort(key=lambda r: r.priority)

    def _load_extensions(self) -> None:
        extensions_config = self._extensions_config or []
        for ext_config in extensions_config:
            if not isinstance(ext_config, dict):
                continue
            name = ext_config.get("name")
            ext_type = ext_config.get("type")
            if ext_type in ("transform", "inline"):
                self._extensions[name] = ext_config

    def find_matching_rule(self, message: Message) -> RoutingRule | None:
        for rule in self._rules:
            if rule.match_message(message):
                return rule
        return None

    def get_default_destination(self) -> list[str]:
        if self._default_action == "discard":
            return []
        elif self._default_action == "keep":
            return [self._default_instance] if self._default_instance else []
        elif self._default_action == "forward":
            return self.config.get("routing", {}).get("default_forward_to", [])
        return []

    async def route(self, message: Message) -> list[Message]:
        results: list[Message] = []
        rule = self.find_matching_rule(message)
        
        if rule and rule.actions:
            transformed_msg = await self._apply_extensions(message, rule.actions.extensions)
            destinations = rule.actions.forward_to
            
            for dest in destinations:
                if dest == "handler":
                    response = await self._call_handler(transformed_msg)
                    if response:
                        results.append(response)
                else:
                    forwarded = self._create_forward_message(transformed_msg, dest)
                    if forwarded:
                        results.append(forwarded)
            
            if rule.actions.keep_in_default and self._default_instance:
                default_msg = self._create_forward_message(transformed_msg, self._default_instance)
                if default_msg:
                    results.append(default_msg)
        else:
            destinations = self.get_default_destination()
            for dest in destinations:
                if dest:
                    forwarded = self._create_forward_message(message, dest)
                    if forwarded:
                        results.append(forwarded)
        
        return results

    async def _apply_extensions(self, message: Message, extension_names: list[str]) -> Message:
        result = message
        for ext_name in extension_names:
            transform_plugin = self._plugin_registry.create_transform(ext_name)
            if transform_plugin:
                try:
                    config = self._extensions.get(ext_name, {}).get("config", {})
                    result = await transform_plugin.transform(result, config)
                except Exception:
                    pass
                continue
            ext_config = self._extensions.get(ext_name)
            if not ext_config:
                continue
            try:
                result = await self._execute_extension(result, ext_config)
            except Exception:
                pass
        return result

    async def _execute_extension(self, message: Message, ext_config: dict[str, Any]) -> Message:
        inner_config = ext_config.get("config", ext_config)
        transforms = inner_config.get("transforms", [])
        result = message
        for transform in transforms:
            if isinstance(transform, dict):
                code = transform.get("code")
                if code:
                    result = await self._execute_code(result, code, transform.get("config", {}))
        return result

    async def _execute_code(self, message: Message, code: str, config: dict[str, Any]) -> Message:
        context = {"msg": message, "config": config}
        try:
            exec(code, context)
            return context.get("msg", message)
        except Exception:
            return message

    async def _call_handler(self, message: Message) -> Message | None:
        if self.exchange._handler:
            try:
                result = self.exchange._handler(message)
                if asyncio.iscoroutine(result):
                    result = await result
                if result:
                    result.from_instance = "handler"
                    return result
            except Exception:
                pass
        return None

    def _create_forward_message(self, message: Message, destination: str) -> Message | None:
        if destination == "handler":
            return None
        return Message(
            id=message.id,
            session_id=message.session_id,
            from_instance=message.from_instance,
            sender=message.sender,
            ts=message.ts,
            text=message.text,
            group_id=message.group_id,
            thread_id=message.thread_id,
            media=message.media,
            interactive=message.interactive,
            actions=message.actions,
            reactions=message.reactions,
            raw=message.raw,
            to=[destination],
            metadata={**message.metadata, "routed_to": destination},
        )

    def get_rules(self) -> list[RoutingRule]:
        return self._rules.copy()

    def add_rule(self, rule: RoutingRule) -> None:
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority)

    def remove_rule(self, name: str) -> bool:
        for i, rule in enumerate(self._rules):
            if rule.name == name:
                del self._rules[i]
                return True
        return False

    def reload(self, config: dict[str, Any] | None = None) -> None:
        if config:
            self.config = config
        self._load_config(self.config)
        self._load_extensions()
    
    def get_warnings(self) -> list[str]:
        """Get warnings from rule loading."""
        return self._warnings.copy()
    
    def validate_rules(self) -> tuple[list[RoutingRule], list[str]]:
        """Validate current rules and return (valid_rules, warnings)."""
        valid = []
        warnings = []
        
        for rule in self._rules:
            has_missing = False
            if rule.actions:
                for ext_name in rule.actions.extensions:
                    if not self._plugin_registry.get_match(ext_name) and not self._plugin_registry.get_transform(ext_name):
                        warnings.append(f"Rule '{rule.name}': plugin '{ext_name}' not found")
                        has_missing = True
            if not has_missing:
                valid.append(rule)
        
        return valid, warnings


def load_rules_from_config(config: dict[str, Any], strict: bool = False) -> tuple[list[RoutingRule], list[str]]:
    """Load routing rules from config with plugin validation.
    
    Returns (rules, warnings).
    """
    from .plugins.base import get_registry
    
    registry = get_registry()
    rules = []
    warnings = []
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
            
            if not rule.enabled:
                continue
            
            if rule.actions:
                for ext_name in rule.actions.extensions:
                    if not registry.get_match(ext_name) and not registry.get_transform(ext_name):
                        msg = f"Plugin '{ext_name}' not found for rule '{rule.name}'"
                        if strict:
                            raise ValueError(msg)
                        warnings.append(msg)
            
            rules.append(rule)
    
    rules.sort(key=lambda r: r.priority)
    return rules, warnings


__all__ = [
    "MatchCondition",
    "RoutingAction",
    "RoutingRule",
    "RuleMatcher",
    "RoutingEngine",
    "load_rules_from_config",
]
