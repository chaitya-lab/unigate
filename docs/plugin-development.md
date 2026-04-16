# Plugin Development Guide

This guide explains how to create plugins for Unigate.

## Plugin Types

| Type | Purpose | Protocol Method |
|------|---------|----------------|
| channel | Receive/send from platform | `to_message()`, `from_message()` |
| match | Check message conditions | `match(msg, value)` |
| transform | Modify message content | `transform(msg, config)` |
| transport | Deliver to external service | `send(msg, config)` |

## File Naming

All plugins live in `src/unigate/plugins/` with flat structure:

```
plugins/
├── base.py              # Registry & protocols
├── channel_web.py       # Web channel
├── channel_telegram.py  # Telegram channel
├── match_text.py       # Text matcher
├── transform_truncate.py # Truncate transform
└── transport_http.py   # HTTP transport
```

Naming convention: `{type}_{name}.py`

## Channel Plugins

### Simple Plugin (for routing)

For basic routing, just implement the receive/send methods:

```python
"""Channel plugin: my_channel"""

from typing import Any

class MyChannelPlugin:
    name = "my_channel"
    type = "channel"
    description = "My custom channel"
    
    async def receive(self, raw: dict[str, Any]) -> Message | None:
        """Convert raw input to Message."""
        # Parse raw data, return Message or None
        return Message(...)
    
    async def send(self, msg: Message) -> dict[str, Any] | None:
        """Convert Message to platform format."""
        return {"text": msg.text}
```

### Full Channel (for lifecycle management)

For channels with setup, health checks, etc.:

```python
from ..channel import BaseChannel, SendResult
from ..capabilities import ChannelCapabilities
from ..lifecycle import HealthStatus, SetupResult, SetupStatus
from ..message import Message, Sender
from ..stores import SecureStore

class MyChannel(BaseChannel):
    """Full channel implementation."""
    
    name = "my_channel"
    transport = "https"
    auth_method = "token"
    
    def __init__(self, instance_id: str, store: SecureStore, kernel: Any, config: dict | None = None):
        self.instance_id = instance_id
        self.store = store
        self.kernel = kernel
        self.config = config or {}
        self._token = None
    
    async def setup(self) -> SetupResult:
        """Initialize the channel.
        
        Return SetupResult with:
        - SetupStatus.READY if ready
        - SetupStatus.NEEDS_INTERACTION if user input required
        - SetupStatus.FAILED if setup failed
        """
        self._token = self.config.get("token") or await self.store.get("token")
        
        if not self._token:
            return SetupResult(
                status=SetupStatus.NEEDS_INTERACTION,
                interaction_type="token",
                interaction_data={"prompt": "Enter your API token:"},
            )
        
        return SetupResult(status=SetupStatus.READY)
    
    async def start(self) -> None:
        """Start the channel (begin polling, connect, etc.)."""
        pass
    
    async def stop(self) -> None:
        """Stop the channel gracefully."""
        pass
    
    def to_message(self, raw: dict) -> Message:
        """Convert raw platform data to Message."""
        return Message(
            id=raw.get("id", ""),
            session_id=raw.get("session_id", ""),
            from_instance=self.instance_id,
            sender=Sender(
                platform_id=raw.get("sender", {}).get("id", ""),
                name=raw.get("sender", {}).get("name", "User"),
            ),
            ts=raw.get("ts"),
            text=raw.get("text", ""),
            raw=raw,
        )
    
    async def from_message(self, msg: Message) -> SendResult:
        """Send Message to platform."""
        # Convert and send
        return SendResult(success=True, provider_message_id="...")
    
    @property
    def capabilities(self) -> ChannelCapabilities:
        """Declare channel capabilities."""
        return ChannelCapabilities(
            direction="bidirectional",
            supports_groups=True,
            supports_threads=False,
            supports_reactions=True,
            supports_reply_to=True,
            supports_media_send=True,
        )
    
    async def health_check(self) -> HealthStatus:
        """Check channel health."""
        if not self._token:
            return HealthStatus.UNKNOWN
        # Check connectivity, return HEALTHY or UNHEALTHY
        return HealthStatus.HEALTHY
```

## Matcher Plugins

Matchers evaluate conditions and return True/False:

```python
from typing import Any
from ..message import Message

class TextContainsMatcher:
    """Match if message text contains substring."""
    
    name = "text_contains"
    type = "match"
    description = "Match if text contains substring"
    
    def match(self, msg: Message, value: str) -> bool:
        """Check if text contains value (case-insensitive)."""
        if not msg.text or not value:
            return False
        return value.lower() in msg.text.lower()


class SenderPatternMatcher:
    """Match sender by glob pattern."""
    
    name = "sender_pattern"
    type = "match"
    description = "Match sender by pattern"
    
    def match(self, msg: Message, value: str) -> bool:
        """Check if sender matches glob pattern."""
        import fnmatch
        if not msg.sender:
            return False
        return fnmatch.fnmatch(msg.sender.platform_id, value)
```

## Transform Plugins

Transforms modify messages:

```python
from typing import Any
from ..message import Message

class TruncateTransform:
    """Truncate message text."""
    
    name = "truncate"
    type = "transform"
    description = "Truncate text to max length"
    
    async def transform(self, msg: Message, config: dict[str, Any]) -> Message:
        """Return truncated message."""
        max_length = config.get("max_length", 4096)
        suffix = config.get("suffix", "...")
        
        if not msg.text or len(msg.text) <= max_length:
            return msg
        
        truncated = msg.text[:max_length - len(suffix)] + suffix
        
        return Message(
            id=msg.id,
            session_id=msg.session_id,
            from_instance=msg.from_instance,
            sender=msg.sender,
            ts=msg.ts,
            text=truncated,
            raw=msg.raw,
            metadata={**msg.metadata, "truncated": True},
        )
```

## Transport Plugins

Transports send to external services:

```python
from typing import Any
import httpx
from ..message import Message

class HTTPTransport:
    """Send via HTTP/HTTPS."""
    
    name = "http"
    type = "transport"
    description = "Send via HTTP POST"
    
    async def send(self, msg: Message, config: dict[str, Any]) -> bool:
        """Send message via HTTP."""
        url = config.get("url")
        if not url:
            return False
        
        headers = config.get("headers", {})
        timeout = config.get("timeout", 30)
        
        payload = {
            "id": msg.id,
            "text": msg.text,
            "sender": {
                "id": msg.sender.platform_id,
                "name": msg.sender.name,
            },
        }
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                return 200 <= response.status_code < 300
        except Exception:
            return False
```

## Registering Plugins

### Built-in Plugins

Add to `_load_builtins()` in `src/unigate/plugins/base.py`:

```python
def _load_builtins(registry: PluginRegistry) -> None:
    from .channel_web import WebChannelPlugin
    from .channel_telegram import TelegramChannelPlugin
    from .channel_my import MyChannel
    # ... more imports
    
    for cls in [
        WebChannelPlugin,
        TelegramChannelPlugin,
        MyChannel,  # Add your plugin
        # ... more
    ]:
        registry.register(cls, "builtin")
```

### User Plugins

Load from plugin directories:

```python
from unigate.plugins.base import register_plugin_dirs

# Load plugins from custom directory
register_plugin_dirs(["/path/to/plugins"])
```

## Testing Your Plugin

```python
import pytest
from unigate.plugins.base import get_registry

def test_my_plugin_registered():
    registry = get_registry()
    assert "channel.my_channel" in registry.channels

@pytest.mark.asyncio
async def test_my_channel_receive():
    registry = get_registry()
    cls = registry.get_channel("my_channel")
    plugin = cls()
    
    raw = {"id": "123", "text": "Hello"}
    msg = await plugin.receive(raw)
    
    assert msg.text == "Hello"
```

## Example: Creating a Slack Channel Plugin

```python
"""Channel plugin: Slack"""

from typing import Any

class SlackChannelPlugin:
    name = "slack"
    type = "channel"
    description = "Slack workspace integration"

class SlackChannel:
    """Slack Channel implementation."""
    
    name = "slack"
    transport = "https"
    auth_method = "token"
    
    def __init__(self, instance_id: str, store, kernel: Any, config: dict | None = None):
        self.instance_id = instance_id
        self.store = store
        self.kernel = kernel
        self.config = config or {}
    
    async def setup(self):
        from ..lifecycle import SetupResult, SetupStatus
        self._token = self.config.get("bot_token") or await self.store.get("bot_token")
        if not self._token:
            return SetupResult(
                status=SetupStatus.NEEDS_INTERACTION,
                interaction_type="token",
                interaction_data={"prompt": "Enter Slack Bot Token:"},
            )
        return SetupResult(status=SetupStatus.READY)
    
    def to_message(self, raw: dict) -> "Message":
        from ..message import Message, Sender
        return Message(
            id=raw.get("event_id", ""),
            session_id=raw.get("channel", ""),
            from_instance=self.instance_id,
            sender=Sender(
                platform_id=raw.get("user", ""),
                name=raw.get("user_name", "User"),
            ),
            ts=raw.get("ts"),
            text=raw.get("text", ""),
            raw=raw,
        )
    
    async def from_message(self, msg: "Message") -> "SendResult":
        # Post to Slack API
        return SendResult(success=True, provider_message_id="...")
```

## Summary

1. **Choose plugin type** - channel, match, transform, or transport
2. **Create file** - `src/unigate/plugins/{type}_{name}.py`
3. **Implement protocol** - Add required methods
4. **Register** - Add to `_load_builtins()` or use plugin directory
5. **Test** - Add tests and verify with `unigate plugins list`
