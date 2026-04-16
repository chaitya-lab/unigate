# Contributing to Unigate

Thank you for contributing to Unigate! This guide covers how to develop new plugins and contribute to the project.

## Plugin Development

Unigate uses a flat plugin structure. All plugins live in `src/unigate/plugins/` with naming prefixes:
- `channel_*.py` - Receive/send messages
- `match_*.py` - Match message conditions
- `transform_*.py` - Transform message content
- `transport_*.py` - Deliver messages externally

### Quick Plugin Template

```python
"""Channel plugin: my_integration"""

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..message import Message


class MyIntegrationPlugin:
    """Short description of what this plugin does."""
    
    name = "my_integration"  # Used as channel.my_integration
    type = "channel"
    description = "Detailed description for plugin list"


class MyIntegrationChannel:
    """Full channel implementation with lifecycle support."""
    
    name = "my_integration"
    transport = "http"
    auth_method = "token"
    
    def __init__(self, instance_id: str, store: Any, kernel: Any, config: dict | None = None):
        self.instance_id = instance_id
        self.store = store
        self.kernel = kernel
        self.config = config or {}
    
    async def setup(self):
        """Initialize the channel. Return SetupResult."""
        from ..lifecycle import SetupResult, SetupStatus
        # Configure connection, validate credentials, etc.
        return SetupResult(status=SetupStatus.READY)
    
    async def start(self):
        """Start the channel (begin polling, connect, etc.)."""
        pass
    
    async def stop(self):
        """Stop the channel gracefully."""
        pass
    
    def to_message(self, raw: dict) -> "Message":
        """Convert raw platform format to Message."""
        from ..message import Message, Sender
        return Message(
            id=raw.get("id", ""),
            session_id=raw.get("session_id", ""),
            from_instance=self.instance_id,
            sender=Sender(
                platform_id=raw.get("sender_id", ""),
                name=raw.get("sender_name", "User"),
            ),
            ts=raw.get("ts"),
            text=raw.get("text", ""),
            raw=raw,
        )
    
    async def from_message(self, msg: "Message") -> SendResult:
        """Convert Message to platform format and send."""
        from ..channel import SendResult
        # Send to platform, return result
        return SendResult(success=True, provider_message_id="...")
    
    @property
    def capabilities(self) -> "ChannelCapabilities":
        """Declare what this channel supports."""
        from ..capabilities import ChannelCapabilities
        return ChannelCapabilities(
            direction="bidirectional",
            supports_groups=True,
            supports_threads=False,
            supports_reactions=True,
            supports_reply_to=True,
        )
    
    async def health_check(self) -> "HealthStatus":
        """Return current health status."""
        from ..lifecycle import HealthStatus
        return HealthStatus.HEALTHY
```

### Register Your Plugin

Add your plugin to `_load_builtins()` in `src/unigate/plugins/base.py`:

```python
from .channel_my_integration import MyIntegrationChannel

for cls in [
    # ... existing plugins
    MyIntegrationChannel,
]:
    registry.register(cls, "builtin")
```

### Matcher Plugin Template

Matchers evaluate if a message matches a condition:

```python
"""Matcher plugin: my_condition"""

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..message import Message


class MyConditionMatcher:
    """Match messages by custom condition."""
    
    name = "my_condition"
    type = "match"
    description = "Match by custom condition"
    
    def match(self, msg: Message, value: Any) -> bool:
        """Return True if message matches.
        
        Args:
            msg: The message to check
            value: The condition value from config
            
        Returns:
            True if message matches, False otherwise
        """
        # Your matching logic here
        return "keyword" in msg.text.lower()
```

### Transform Plugin Template

Transforms modify message content:

```python
"""Transform plugin: my_transform"""

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..message import Message


class MyTransform:
    """Transform message content."""
    
    name = "my_transform"
    type = "transform"
    description = "Transform message text"
    
    async def transform(self, msg: Message, config: dict[str, Any]) -> Message:
        """Transform and return the message.
        
        Args:
            msg: The message to transform
            config: Configuration for the transform
            
        Returns:
            The transformed message
        """
        # Your transformation logic here
        return Message(
            # ... copy all fields from msg ...
            text=msg.text.upper(),  # Example: uppercase
        )
```

### Transport Plugin Template

Transports deliver messages externally:

```python
"""Transport plugin: my_transport"""

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..message import Message


class MyTransport:
    """Send messages via custom transport."""
    
    name = "my_transport"
    type = "transport"
    description = "Send via custom transport"
    
    async def send(self, msg: Message, config: dict[str, Any]) -> bool:
        """Send message to external service.
        
        Args:
            msg: The message to send
            config: Transport configuration
            
        Returns:
            True if sent successfully, False otherwise
        """
        # Your sending logic here
        url = config.get("url")
        # ... send message ...
        return True
```

## Running Tests

```powershell
# All tests
python -m pytest tests/ -v

# Specific test file
python -m pytest tests/test_plugins.py -v

# With coverage
python -m pytest tests/ --cov=src/unigate
```

## Code Style

- Use type hints throughout
- Follow existing conventions in the codebase
- Add docstrings for public APIs
- Keep functions small and focused

## Commit Guidelines

1. **One feature per commit** - Each commit should do one thing
2. **Descriptive messages** - Explain what and why, not just what
3. **Test your changes** - Add tests for new features
4. **Update docs** - Update README and docs as needed

Example:
```
Add WhatsApp channel plugin

- Implement WhatsAppChannel with full Business API support
- Support text, media, location, and interactive messages
- Add webhook verification
- Include health checks
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Add tests
5. Ensure all tests pass
6. Update documentation
7. Submit a pull request

## Questions?

Open an issue on GitHub or reach out to the maintainers.
