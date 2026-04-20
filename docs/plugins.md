# Plugins

Unigate uses a plugin system for extensibility. Plugins can be:

- **Channels** - Receive and send messages
- **Matchers** - Match message conditions for routing
- **Transforms** - Modify messages in the pipeline
- **Transports** - Delivery methods for outbound messages

---

## Plugin Directory

All plugins live in `src/unigate/plugins/`:

```
src/unigate/plugins/
├── base.py                    # Plugin registry & protocols
├── channel_web.py            # Web webhook channel
├── channel_webui.py          # Web UI channel
├── channel_telegram.py        # Telegram channel
├── channel_whatsapp.py       # WhatsApp channel
├── match_text.py              # Text matcher
├── match_sender.py           # Sender matcher
├── match_media.py            # Media matcher
├── match_time.py             # Time matcher
├── transform_truncate.py     # Truncate transform
├── transform_extract.py      # Extract transform
├── transform_add.py          # Add metadata transform
├── transport_http.py         # HTTP transport
├── transport_websocket.py    # WebSocket transport
└── transport_ftp.py          # FTP transport
```

---

## Creating a Channel Plugin

Channels receive inbound messages and send outbound messages.

### Basic Channel

```python
# src/unigate/plugins/channel_hello.py
from typing import Any
from ..capabilities import ChannelCapabilities
from ..channel import BaseChannel, SendResult
from ..lifecycle import SetupResult
from ..message import Message

class HelloChannel(BaseChannel):
    """Simple console-based channel for testing."""
    
    name = "hello"
    transport = "stdio"
    auth_method = "none"
    
    async def setup(self) -> SetupResult:
        """Called once at startup."""
        return SetupResult.READY
    
    async def start(self) -> None:
        """Called when instance starts. Begin listening."""
        print(f"Hello channel '{self.instance_id}' started!")
    
    async def stop(self) -> None:
        """Called when instance stops. Clean up."""
        print(f"Hello channel '{self.instance_id}' stopped!")
    
    def to_message(self, raw: dict[str, Any]) -> Message:
        """Convert platform format to Message."""
        return Message(
            id=raw.get("id", "unknown"),
            from_instance=self.instance_id,
            sender={
                "id": raw.get("sender_id", "anonymous"),
                "name": raw.get("sender_name", "Anonymous"),
            },
            text=raw.get("text", ""),
        )
    
    async def from_message(self, msg: Message) -> SendResult:
        """Send Message to platform."""
        print(f"[{self.instance_id}] {msg.text}")
        return SendResult(success=True)
    
    @property
    def capabilities(self) -> ChannelCapabilities:
        """Declare channel capabilities."""
        return ChannelCapabilities(
            direction="bidirectional",
            supports_media_send=True,
            supported_media_types=["image", "video", "audio"],
        )
```

### Webhook Channel

For HTTP-based channels that receive webhooks:

```python
# src/unigate/plugins/channel_myapi.py
from typing import Any
from ..capabilities import ChannelCapabilities
from ..channel import BaseChannel, RawRequest, SendResult
from ..lifecycle import SetupResult
from ..message import Message

class MyAPIChannel(BaseChannel):
    """Channel that receives webhooks."""
    
    name = "myapi"
    transport = "http"
    auth_method = "hmac"
    
    async def setup(self) -> SetupResult:
        """Verify credentials."""
        return SetupResult.READY
    
    async def start(self) -> None:
        """Nothing to start for webhook-based channel."""
        pass
    
    async def stop(self) -> None:
        """Nothing to stop."""
        pass
    
    async def verify_signature(self, request: RawRequest) -> bool:
        """Verify webhook signature."""
        import hmac
        import hashlib
        
        secret = await self.store.get("secret")
        if not secret:
            secret = self.config.get("secret", "")
        
        signature = request.headers.get("x-signature", "")
        expected = hmac.new(
            secret.encode(),
            request.body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected)
    
    def to_message(self, raw: dict[str, Any]) -> Message:
        """Convert webhook payload to Message."""
        return Message(
            id=raw.get("message_id"),
            from_instance=self.instance_id,
            sender={
                "id": str(raw.get("user_id")),
                "name": raw.get("user_name", ""),
            },
            text=raw.get("text"),
            media=raw.get("attachments", []),
        )
    
    async def from_message(self, msg: Message) -> SendResult:
        """Send response back via API."""
        import aiohttp
        
        api_url = self.config.get("api_url")
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"{api_url}/send",
                json={"text": msg.text}
            )
        return SendResult(success=True)
    
    @property
    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(
            direction="bidirectional",
            supports_media_send=True,
            supports_reply_to=True,
        )
```

### Polling Channel

For channels that poll an API:

```python
# src/unigate/plugins/channel_poll.py
import asyncio
from typing import Any
from ..capabilities import ChannelCapabilities
from ..channel import BaseChannel, SendResult
from ..lifecycle import SetupResult
from ..message import Message

class PollChannel(BaseChannel):
    """Channel that polls an API for new messages."""
    
    name = "poll"
    transport = "http"
    auth_method = "token"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._running = False
        self._task = None
    
    async def setup(self) -> SetupResult:
        """Get auth token."""
        return SetupResult.READY
    
    async def start(self) -> None:
        """Start polling loop."""
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
    
    async def stop(self) -> None:
        """Stop polling."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _poll_loop(self) -> None:
        """Poll for new messages."""
        while self._running:
            try:
                messages = await self._fetch_messages()
                for raw in messages:
                    msg = self.to_message(raw)
                    # This triggers the routing pipeline
                    await self.kernel.emit_inbound(msg)
            except Exception as e:
                print(f"Poll error: {e}")
            
            await asyncio.sleep(5)  # Poll every 5 seconds
    
    async def _fetch_messages(self) -> list[dict]:
        """Fetch new messages from API."""
        # Implement API call here
        return []
    
    def to_message(self, raw: dict[str, Any]) -> Message:
        return Message(
            id=raw.get("id"),
            from_instance=self.instance_id,
            sender={"id": raw.get("user_id")},
            text=raw.get("text"),
        )
    
    async def from_message(self, msg: Message) -> SendResult:
        # Send via API
        return SendResult(success=True)
    
    @property
    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(direction="bidirectional")
```

---

## Creating a Matcher Plugin

Matchers check if a message matches certain conditions.

```python
# src/unigate/plugins/match_custom.py
from typing import Any
from ..routing import BaseMatcher, MatcherResult

class CustomMatcher(BaseMatcher):
    """Match messages based on custom logic."""
    
    name = "custom"
    
    def match(self, msg: Message, config: dict[str, Any]) -> MatcherResult:
        """Return (matched: bool, reason: str)"""
        
        # Example: Match if text contains specific keyword
        keyword = config.get("keyword", "")
        if keyword and msg.text and keyword in msg.text:
            return MatcherResult(True, f"Contains '{keyword}'")
        
        # Example: Match if sender is in allow list
        allow_list = config.get("allow_list", [])
        if allow_list and msg.sender.get("id") in allow_list:
            return MatcherResult(True, "Sender in allow list")
        
        return MatcherResult(False, "")
    
    @property
    def schema(self) -> dict[str, Any]:
        """JSON Schema for config validation."""
        return {
            "type": "object",
            "properties": {
                "keyword": {"type": "string"},
                "allow_list": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            }
        }
```

---

## Creating a Transform Plugin

Transforms modify messages in the pipeline.

```python
# src/unigate/plugins/transform_censor.py
from ..message import Message
from ..extensions import BaseExtension, ExtensionContext

class CensorTransform(BaseExtension):
    """Censor specific words in messages."""
    
    name = "censor"
    priority = 20  # Run after inbound processing
    
    async def process_inbound(
        self, msg: Message, ctx: ExtensionContext
    ) -> Message | None:
        """Censor words in inbound message."""
        if not msg.text:
            return msg
        
        censored = msg.text
        for word in ctx.config.get("words", []):
            censored = censored.replace(word, ctx.config.get("replacement", "***"))
        
        msg.text = censored
        return msg
    
    async def process_outbound(
        self, msg: Message, ctx: ExtensionContext
    ) -> Message | None:
        """Censor words in outbound message."""
        return self.process_inbound(msg, ctx)
```

---

## Creating a Transport Plugin

Transports deliver messages to destinations.

```python
# src/unigate/plugins/transport_custom.py
import aiohttp
from ..message import Message
from ..transports import BaseTransport, TransportResult

class CustomTransport(BaseTransport):
    """Send messages via custom API."""
    
    name = "custom"
    
    async def send(
        self, msg: Message, config: dict[str, Any]
    ) -> TransportResult:
        """Send message via custom transport."""
        api_url = config.get("url")
        api_key = config.get("api_key")
        
        headers = {"Authorization": f"Bearer {api_key}"}
        payload = {
            "text": msg.text,
            "recipient": msg.receiver_id,
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    api_url,
                    json=payload,
                    headers=headers
                ) as resp:
                    if resp.status == 200:
                        return TransportResult(success=True)
                    else:
                        return TransportResult(
                            success=False,
                            error=f"HTTP {resp.status}"
                        )
        except Exception as e:
            return TransportResult(success=False, error=str(e))
```

---

## Registering Plugins

Plugins are auto-registered by naming convention:

| Type | Naming | Example |
|------|--------|---------|
| Channel | `channel_*.py` | `channel_telegram.py` |
| Matcher | `match_*.py` | `match_text.py` |
| Transform | `transform_*.py` | `transform_truncate.py` |
| Transport | `transport_*.py` | `transport_http.py` |

Each class needs these class attributes:

### Channel Class Attributes

```python
class MyChannel(BaseChannel):
    name = "mychannel"           # Used in config
    type = "channel"            # Must be "channel"
    transport = "http"          # http, websocket, tcp, stdio
    auth_method = "token"       # none, token, hmac, oauth, qr
```

### Matcher Class Attributes

```python
class MyMatcher:
    name = "mymatcher"          # Used in routing rules
    type = "match"             # Must be "match"
```

### Transform Class Attributes

```python
class MyTransform:
    name = "mytransform"        # Used in extensions
    type = "transform"         # Must be "transform"
```

---

## Using Custom Plugins

### Add to Config

```yaml
# unigate.yaml
unigate:
  plugin_dirs:
    - ./my_plugins              # Your custom plugins
  loaded_plugins: "*"          # Or specific patterns
  disabled_plugins: []        # Exclude specific plugins

instances:
  my_channel:
    type: mychannel
    # ... config
```

### Plugin Filtering

```yaml
unigate:
  plugin_dirs:
    - ./src/unigate/plugins
    - ./my_plugins
  
  # Load specific patterns (fnmatch syntax)
  loaded_plugins:
    - "channel.*"        # All channels
    - "match.text_*"     # Text matchers only
    - "transform.*"
    - "transport.http"
  
  # Exclude specific plugins
  disabled_plugins:
    - "channel.telegram"
    - "match.day_of_week"
```

Common patterns:
- `"*"` - All plugins (default)
- `"channel.*"` - All channels
- `"match.*"` - All matchers
- `"transform.*"` - All transforms
- `"transport.*"` - All transports

### Plugin Directory Structure

```
my_plugins/
├── __init__.py
├── channel_mine.py
├── match_mine.py
└── transform_mine.py
```

---

## Plugin Capabilities

Channels can declare capabilities that affect behavior:

```python
@property
def capabilities(self) -> ChannelCapabilities:
    return ChannelCapabilities(
        direction="bidirectional",  # inbound | outbound | bidirectional
        supports_threads=True,
        supports_reactions=True,
        supports_groups=True,
        supports_reply_to=True,
        supports_edit=False,
        supports_delete=False,
        supports_typing_indicator=True,
        supports_media_send=True,
        supported_media_types=["image", "video", "audio", "file"],
        supported_interaction_types=["confirm", "select"],
        max_message_length=4096,
        max_media_size_bytes=10485760,  # 10MB
        streaming_mode="none",  # none | typing_only | edit | chunked | real
    )
```

---

## Best Practices

### Error Handling

```python
async def from_message(self, msg: Message) -> SendResult:
    try:
        await self._send(msg)
        return SendResult(success=True)
    except RateLimitError:
        # Let kernel handle retry
        raise
    except AuthError:
        # Move to dead letters
        return SendResult(success=False, permanent=True)
    except Exception as e:
        # Retry
        return SendResult(success=False, error=str(e))
```

### Logging

```python
import logging

logger = logging.getLogger(__name__)

class MyChannel(BaseChannel):
    async def start(self) -> None:
        logger.info(f"Starting {self.instance_id}")
    
    async def from_message(self, msg: Message) -> SendResult:
        logger.debug(f"Sending to {msg.receiver_id}")
```

### Health Checks

```python
async def health_check(self) -> HealthStatus:
    """Return current health state."""
    try:
        await self._check_connection()
        return HealthStatus.HEALTHY
    except ConnectionError:
        return HealthStatus.UNHEALTHY
    except TimeoutError:
        return HealthStatus.DEGRADED
```

---

## Testing Plugins

```python
import pytest
from unigate.testing import FakeChannel, TestKit

@pytest.mark.asyncio
async def test_my_channel():
    kit = TestKit()
    channel = FakeChannel(instance_id="test")
    kit.add_instance(channel)
    
    @kit.on_message
    async def handle(msg: Message) -> Message:
        return Message(to=[], session_id=msg.session_id, text="ok")
    
    await kit.start()
    
    # Inject test message
    await channel.inject(text="hello")
    
    # Check response
    response = await channel.next_sent()
    assert response.text == "ok"
    
    await kit.stop()
```

---

## Next Steps

- [Configuration](configuration.md) - Use plugins in config
- [Routing](routing.md) - Route based on plugin conditions
- [Architecture](../architecture.md) - System design
