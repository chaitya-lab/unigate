"""Identity extension - links users across platforms.

This extension demonstrates how to implement cross-platform user identity.
It's NOT enabled by default - enable it in config if you need it.

Example: SMS and WhatsApp both have phone number +1234567890.
Without extension: Different sessions for each platform.
With extension: Same canonical_id, can track across platforms.

Usage in config:
    extensions:
      - name: identity
        config:
          identity_map:
            "+1234567890": alice
          auto_detect: true
"""

from __future__ import annotations

from typing import Any, ClassVar

from ..events import KernelEvent
from ..extensions import ExtensionDecision, InboundExtension, EventExtension
from ..message import Message


class IdentityExtension:
    """Links users across platforms using canonical_id.
    
    This extension populates sender.canonical_id for cross-platform identity.
    When enabled, the same user on different platforms will have the same canonical_id.
    
    Configuration:
        identity_map: dict mapping platform_id to canonical_id
        auto_detect: bool - auto-detect by phone/email matching
    
    Usage:
        # Config
        extensions:
          - name: identity
        
        # In handler:
        if msg.sender.canonical_id == "alice":
            # Same user on any platform
    """
    
    name: ClassVar[str] = "identity"
    priority: ClassVar[int] = 5  # Runs early to populate canonical_id
    
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}
        self._identity_map: dict[str, str] = self._config.get("identity_map", {})
        self._auto_detect: bool = self._config.get("auto_detect", False)
    
    async def handle(self, msg: Message) -> ExtensionDecision:
        """Populate canonical_id for cross-platform identity."""
        platform_id = msg.sender.platform_id
        
        # Check explicit mapping
        if platform_id in self._identity_map:
            canonical = self._identity_map[platform_id]
            msg.sender.canonical_id = canonical
        
        # Auto-detect by phone number patterns
        elif self._auto_detect:
            if self._looks_like_phone(platform_id):
                canonical = self._normalize_phone(platform_id)
                msg.sender.canonical_id = canonical
        
        return ExtensionDecision(continue_flow=True, message=msg)
    
    async def on_event(self, event: KernelEvent) -> None:
        """Track user identity across messages."""
        pass
    
    @staticmethod
    def _looks_like_phone(value: str) -> bool:
        """Simple check if value looks like a phone number."""
        cleaned = value.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
        return cleaned.isdigit() and len(cleaned) >= 10
    
    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """Normalize phone number for matching."""
        return phone.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")


__all__ = ["IdentityExtension"]
