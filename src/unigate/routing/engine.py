"""Routing engine - evaluates rules and routes messages."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from ..message import Message
from ..transforms import get_transform_registry
from .rule import MatchCondition, RoutingAction, RoutingRule, load_rules_from_config

if TYPE_CHECKING:
    from ..kernel import Exchange


class RoutingEngine:
    """
    Routes messages based on configurable rules.
    
    Flow:
    1. Message arrives from channel
    2. Find matching rule (priority order)
    3. Run extensions (transforms)
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
        self._transform_registry = get_transform_registry()
        self._default_action: str = "keep"
        self._default_instance: str | None = "default"
        self._unprocessed_retention_days: int = 7
        self._routing_enabled: bool = True
        
        self._load_config(self.config)
        self._load_extensions()

    def _load_config(self, config: dict[str, Any]) -> None:
        """Load routing configuration."""
        routing = config.get("routing", {})
        
        # Default action for unmatched messages
        self._default_action = routing.get("default_action", "keep")
        
        # Default instance
        self._default_instance = routing.get("default_instance")
        
        # Unprocessed retention
        unprocessed = routing.get("unprocessed", {})
        self._unprocessed_retention_days = unprocessed.get("retention_days", 7)
        
        # Load rules
        self._rules = load_rules_from_config(config)
        
        # Load rules from external file if specified
        rules_file = routing.get("rules_file")
        if rules_file:
            self._load_rules_from_file(rules_file)

    def _load_rules_from_file(self, filepath: str) -> None:
        """Load additional rules from external file."""
        import yaml
        from pathlib import Path
        
        path = Path(filepath)
        if path.exists():
            with open(path) as f:
                data = yaml.safe_load(f)
            if data:
                file_rules = load_rules_from_config(data)
                # Merge with existing rules
                existing_names = {r.name for r in self._rules}
                for rule in file_rules:
                    if rule.name not in existing_names:
                        self._rules.append(rule)
                # Re-sort by priority
                self._rules.sort(key=lambda r: r.priority)

    def _load_extensions(self) -> None:
        """Load transform extensions from config."""
        extensions_config = self.config.get("extensions", [])
        
        for ext_config in extensions_config:
            if not isinstance(ext_config, dict):
                continue
            
            name = ext_config.get("name")
            ext_type = ext_config.get("type")
            
            if ext_type == "transform":
                self._extensions[name] = ext_config

    def find_matching_rule(self, message: Message) -> RoutingRule | None:
        """Find the first matching rule for a message (priority order)."""
        for rule in self._rules:
            if rule.match_message(message):
                return rule
        return None

    def get_default_destination(self) -> list[str]:
        """Get destination for unmatched messages."""
        if self._default_action == "discard":
            return []
        elif self._default_action == "keep":
            return [self._default_instance] if self._default_instance else []
        elif self._default_action == "forward":
            return self.config.get("routing", {}).get("default_forward_to", [])
        return []

    async def route(self, message: Message) -> list[Message]:
        """
        Route a message through the routing engine.
        
        Returns list of messages to forward to each destination.
        """
        results: list[Message] = []
        
        # Find matching rule
        rule = self.find_matching_rule(message)
        
        if rule and rule.actions:
            # Apply extensions
            transformed_msg = await self._apply_extensions(message, rule.actions.extensions)
            
            # Get destinations
            destinations = rule.actions.forward_to
            
            # Forward to each destination
            for dest in destinations:
                if dest == "handler":
                    # Handler receives the message
                    response = await self._call_handler(transformed_msg)
                    if response:
                        results.append(response)
                else:
                    # Forward to instance
                    forwarded = self._create_forward_message(transformed_msg, dest)
                    if forwarded:
                        results.append(forwarded)
            
            # Keep in default instance?
            if rule.actions.keep_in_default and self._default_instance:
                default_msg = self._create_forward_message(transformed_msg, self._default_instance)
                if default_msg:
                    results.append(default_msg)
        else:
            # No matching rule - use default action
            destinations = self.get_default_destination()
            for dest in destinations:
                if dest:
                    forwarded = self._create_forward_message(message, dest)
                    if forwarded:
                        results.append(forwarded)
        
        return results

    async def _apply_extensions(
        self, 
        message: Message, 
        extension_names: list[str]
    ) -> Message:
        """Apply extensions in order to the message."""
        result = message
        
        for ext_name in extension_names:
            transform = self._transform_registry.create(ext_name)
            if transform:
                try:
                    config = self._extensions.get(ext_name, {}).get("config", {})
                    result = await transform.transform(result, config)
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

    async def _execute_extension(
        self, 
        message: Message, 
        ext_config: dict[str, Any]
    ) -> Message:
        """Execute a single extension from config."""
        transforms = ext_config.get("transforms", [])
        
        result = message
        for transform in transforms:
            if isinstance(transform, dict):
                code = transform.get("code")
                if code:
                    result = await self._execute_code(result, code, transform.get("config", {}))
        
        return result

    async def _execute_code(
        self, 
        message: Message, 
        code: str, 
        config: dict[str, Any]
    ) -> Message:
        """Execute code transformation on message."""
        context = {
            "msg": message,
            "config": config,
        }
        
        try:
            exec(code, context)
            return context.get("msg", message)
        except Exception:
            return message

    async def _call_handler(self, message: Message) -> Message | None:
        """Call the registered handler with the message."""
        if self.exchange._handler:
            try:
                result = self.exchange._handler(message)
                if asyncio.iscoroutine(result):
                    result = await result
                if result:
                    # Set the destination back to original sender
                    result.from_instance = "handler"
                    return result
            except Exception:
                pass
        return None

    def _create_forward_message(
        self, 
        message: Message, 
        destination: str
    ) -> Message | None:
        """Create a new message for forwarding to destination."""
        if destination == "handler":
            # Don't create new message for handler
            return None
        
        # Create a forwarded message
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
            metadata={**message.metadata, "routed_to": destination},
        )

    def get_rules(self) -> list[RoutingRule]:
        """Get all routing rules."""
        return self._rules.copy()

    def add_rule(self, rule: RoutingRule) -> None:
        """Add a routing rule."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority)

    def remove_rule(self, name: str) -> bool:
        """Remove a routing rule by name."""
        for i, rule in enumerate(self._rules):
            if rule.name == name:
                del self._rules[i]
                return True
        return False

    def reload(self, config: dict[str, Any] | None = None) -> None:
        """Reload configuration."""
        if config:
            self.config = config
        self._load_config(self.config)
        self._load_extensions()
