"""Identity extension - maps sender IDs to friendly names and links across platforms.

Usage in instance config or global config:

# Option 1: Per-instance identity mapping
instances:
  sales_bot:
    type: telegram
    identity:
      # Map sender IDs to friendly names
      names:
        "123456789": "Alice"
        "987654321": "Bob"
      # Link across platforms
      links:
        "+1234567890": "alice"  # Phone number → canonical ID
      auto_detect: true

# Option 2: Global identity config
identity:
  names:
    "123456789": "Alice"  # telegram:123456789 → Alice
    "+1234567890": "Bob"  # whatsapp:+1234567890 → Bob
  links:
    "alice":
      - "telegram:123456789"
      - "whatsapp:+1234567890"

In handler:
  msg.sender.name  # Friendly name (Alice)
  msg.sender.canonical_id  # Cross-platform ID (alice)
"""

from __future__ import annotations

from typing import Any, ClassVar

from ..events import KernelEvent
from ..extensions import ExtensionDecision, InboundExtension, EventExtension
from ..message import Message


class IdentityExtension:
    """Maps sender IDs to friendly names and links users across platforms.
    
    Configuration options:
    
    # Simple name mapping (ID → display name)
    identity:
      names:
        "123456789": "Alice"
        "+1234567890": "Bob"
    
    # Cross-platform linking (all IDs → canonical ID)
    identity:
      links:
        "alice":
          - "telegram:123456789"
          - "whatsapp:+1234567890"
          - "+1234567890"  # Also match by phone
    
    # Auto-detect identifier types
    identity:
      auto_detect:
        - type: phone
          pattern: "^[+]?[0-9]{10,}$"
        - type: email
          pattern: "^.+@.+\\..+$"
    
    Priority: 5 (runs early to populate canonical_id and name)
    """
    
    name: ClassVar[str] = "identity"
    priority: ClassVar[int] = 5
    
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}
        
        # Name mappings: ID → display name
        self._names: dict[str, str] = {}
        name_config = self._config.get("names", {})
        if isinstance(name_config, dict):
            self._names = name_config
        
        # Cross-platform links: canonical ID → list of platform IDs
        self._links: dict[str, list[str]] = {}
        links_config = self._config.get("links", {})
        if isinstance(links_config, dict):
            for canonical_id, platform_ids in links_config.items():
                if isinstance(platform_ids, list):
                    self._links[canonical_id] = platform_ids
        
        # Auto-detect settings
        self._auto_detect = self._config.get("auto_detect", True)
        self._auto_patterns = self._config.get("auto_patterns", [
            {"type": "phone", "pattern": r"^[+]?[0-9]{10,}$"},
            {"type": "email", "pattern": r"^.+@.+\..+$"},
        ])
    
    async def handle(self, msg: Message) -> ExtensionDecision:
        """Process message to set canonical_id and friendly name."""
        sender_id = msg.sender.platform_id
        instance_id = msg.from_instance
        
        # Key for looking up in mappings
        # Try: instance:sender_id, sender_id (exact), sender_id without instance prefix
        lookup_keys = [
            f"{instance_id}:{sender_id}",  # telegram:123456789
            sender_id,                      # 123456789 or +1234567890
        ]
        
        # 1. Set canonical_id from links
        canonical = self._find_canonical_id(sender_id, instance_id)
        if canonical:
            msg.sender.canonical_id = canonical
        
        # 2. Set friendly name from names mapping
        friendly_name = self._find_name(sender_id, instance_id)
        if friendly_name:
            msg.sender.name = friendly_name
        
        # 3. Auto-detect identifier type and set canonical_id
        if self._auto_detect and not msg.sender.canonical_id:
            detected = self._auto_detect_id(sender_id)
            if detected:
                msg.sender.canonical_id = detected
        
        return ExtensionDecision(continue_flow=True, message=msg)
    
    def _find_canonical_id(self, sender_id: str, instance_id: str) -> str | None:
        """Find canonical ID for a sender."""
        # Check links: sender_id → canonical_id
        for canonical_id, platform_ids in self._links.items():
            for pid in platform_ids:
                if pid == sender_id or pid == f"{instance_id}:{sender_id}":
                    return canonical_id
        return None
    
    def _find_name(self, sender_id: str, instance_id: str) -> str | None:
        """Find friendly name for a sender."""
        lookup_keys = [
            f"{instance_id}:{sender_id}",
            sender_id,
        ]
        for key in lookup_keys:
            if key in self._names:
                return self._names[key]
        return None
    
    def _auto_detect_id(self, sender_id: str) -> str | None:
        """Auto-detect identifier type and normalize."""
        import re
        
        for pattern_config in self._auto_patterns:
            pattern = pattern_config.get("pattern", "")
            id_type = pattern_config.get("type", "unknown")
            
            if re.match(pattern, sender_id):
                # Normalize and use as canonical ID
                normalized = self._normalize_id(sender_id, id_type)
                return f"{id_type}:{normalized}"
        
        return None
    
    def _normalize_id(self, value: str, id_type: str) -> str:
        """Normalize identifier based on type."""
        if id_type == "phone":
            # Remove all non-digits except leading +
            if value.startswith("+"):
                return "+" + "".join(c for c in value if c.isdigit())
            return "".join(c for c in value if c.isdigit())
        return value


__all__ = ["IdentityExtension"]
