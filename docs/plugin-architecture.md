# Unified Plugin System

## Overview

Unigate uses a **flat plugin structure** with naming conventions. Each plugin file can contain one or more plugins of any type. The system auto-discovers plugins from configured directories.

All plugins operate on the **universal Message format**.

---

## Plugin Types

| Type | Interface | Description |
|------|----------|-------------|
| **channel** | `ChannelPlugin` | Receives raw input, converts to Message |
| **match** | `MatcherPlugin` | Evaluates Message → bool (should route?) |
| **transform** | `TransformPlugin` | Modifies Message → Message |
| **transport** | `TransportPlugin` | Delivers Message to external service |

---

## File Structure

```
src/unigate/
├── plugins/                 # Flat plugin structure
│   ├── base.py              # PluginRegistry, base classes, protocols
│   ├── channel_web.py        # Web channel plugin
│   ├── channel_telegram.py   # Telegram channel plugin
│   ├── channel_whatsapp.py   # WhatsApp channel plugin
│   ├── channel_webui.py      # WebUI channel plugin
│   ├── match_from.py        # From matcher
│   ├── match_text.py        # Text matchers
│   ├── match_sender.py      # Sender matchers
│   ├── match_media.py      # Media matchers
│   ├── match_time.py       # Time matchers
│   ├── transform_truncate.py
│   ├── transform_extract.py
│   ├── transform_add.py
│   ├── transport_http.py
│   ├── transport_websocket.py
│   └── transport_ftp.py
├── routing.py              # Routing engine (single file)
├── kernel.py               # Exchange kernel
├── lifecycle.py            # Instance lifecycle
└── stores.py               # Storage backends
```

---

## Plugin Interfaces

### Channel Plugin
```python
class ChannelPlugin:
    name: str           # Plugin identifier
    type: str = "channel"
    
    async def receive(self, raw: dict) -> Message | None:
        """Convert raw input to Message."""
        ...
    
    async def send(self, msg: Message) -> dict | None:
        """Convert Message to platform-specific format."""
        ...
```

### Matcher Plugin
```python
class MatcherPlugin:
    name: str           # e.g., "from", "text_contains", "has_attachment"
    type: str = "match"
    
    def match(self, msg: Message, value: Any) -> bool:
        """Check if message matches condition."""
        ...
```

### Transform Plugin
```python
class TransformPlugin:
    name: str           # e.g., "truncate", "extract_subject"
    type: str = "transform"
    
    async def transform(self, msg: Message, config: dict) -> Message:
        """Modify message. Return modified message."""
        ...
```

### Transport Plugin
```python
class TransportPlugin:
    name: str           # e.g., "http", "ftp", "websocket"
    type: str = "transport"
    
    async def send(self, msg: Message, config: dict) -> bool:
        """Send message externally. Return success."""
        ...
```

---

## Naming Convention

Files use prefixes for organization (not folders):

| Prefix | Example | Contains |
|--------|---------|----------|
| `channel_` | `channel_telegram.py` | Channel plugins |
| `match_` | `match_text.py` | Matcher plugins |
| `transform_` | `transform_truncate.py` | Transform plugins |
| `transport_` | `transport_ftp.py` | Transport plugins |

A single file can contain multiple plugins:
```python
# channel_whatsapp.py - Can contain:
# - ChannelPlugin (WhatsAppChannel)
# - TransformPlugin (whatsapp_cleanup)
# - MatcherPlugin (whatsapp_template)
```

---

## Routing Rules (Config, Not Plugins)

Routing rules reference plugins by name:

```yaml
# unigate.yaml
routing:
  default_action: keep
  rules:
    - name: urgent_to_sms
      priority: 100
      match:
        from_instance: telegram
        text_contains: URGENT
      actions:
        forward_to: [sms_channel]

    - name: vip_users
      priority: 50
      match:
        sender_pattern: "vip_*"
      actions:
        forward_to: [vip_channel]
        keep_in_default: true
```

---

## Built-in Plugins

### Channels
| Plugin | File | Description |
|--------|------|-------------|
| web | `channel_web.py` | HTTP webhook receiver |
| telegram | `channel_telegram.py` | Telegram Bot API |
| whatsapp | `channel_whatsapp.py` | WhatsApp Business API |
| webui | `channel_webui.py` | Web UI for testing |

### Matchers
| Plugin | File | Description |
|--------|------|-------------|
| from | `match_from.py` | Match by source instance |
| sender | `match_sender.py` | Match by sender ID |
| sender_pattern | `match_sender.py` | Match sender by glob pattern |
| text_contains | `match_text.py` | Match text content |
| text_pattern | `match_text.py` | Match text with regex |
| has_media | `match_media.py` | Match by media presence |
| has_attachment | `match_media.py` | Match by attachment |
| day_of_week | `match_time.py` | Match by day of week |
| hour_of_day | `match_time.py` | Match by hour |

### Transforms
| Plugin | File | Description |
|--------|------|-------------|
| truncate | `transform_truncate.py` | Truncate text length |
| extract_subject | `transform_extract.py` | Extract email subject |
| add_metadata | `transform_add.py` | Add metadata fields |
| add_timestamp | `transform_add.py` | Add timestamp |

### Transports
| Plugin | File | Description |
|--------|------|-------------|
| http | `transport_http.py` | HTTP webhook push |
| websocket | `transport_websocket.py` | WebSocket push |
| ftp | `transport_ftp.py` | FTP/SFTP upload |
| file | `transport_ftp.py` | Local file output |

---

## CLI Commands

```bash
# List plugins
unigate plugins list

# Filter by type
unigate plugins list --type channel

# Plugin status
unigate plugins status
unigate plugins status <name>

# Enable/disable
unigate plugins enable <name>
unigate plugins disable <name>

# Generate config
unigate plugins gen-config
unigate plugins gen-config --output config.yaml

# Validate config
unigate plugins validate --config config.yaml
```

---

## Registering Plugins

### Built-in Plugins

Add to `_load_builtins()` in `src/unigate/plugins/base.py`:

```python
def _load_builtins(registry: PluginRegistry) -> None:
    from .channel_my_plugin import MyChannel
    
    for cls in [
        MyChannel,
        # ... other plugins
    ]:
        registry.register(cls, "builtin")
```

### Custom Plugin Directories

```yaml
# unigate.yaml
unigate:
  plugin_dirs:
    - ./plugins
    - ./custom_plugins
```

---

## Example: Creating a Custom Channel

```python
# plugins/channel_mychannel.py
from typing import Any
from ..message import Message, Sender

class MyChannelPlugin:
    name = "mychannel"
    type = "channel"
    description = "My custom channel"
    
    async def receive(self, raw: dict[str, Any]) -> Message | None:
        return Message(
            id=raw.get("id", ""),
            session_id=raw.get("session_id", ""),
            from_instance=self.name,
            sender=Sender(
                platform_id=raw.get("user_id", ""),
                name=raw.get("user_name", "User"),
            ),
            text=raw.get("text", ""),
            raw=raw,
        )
    
    async def send(self, msg: Message) -> dict[str, Any] | None:
        return {"text": msg.text}
```

---

## Example: Creating a Custom Transform

```python
# plugins/transform_prefix.py
from typing import Any
from ..message import Message

class PrefixTransform:
    name = "prefix"
    type = "transform"
    
    async def transform(self, msg: Message, config: dict[str, Any]) -> Message:
        prefix = config.get("prefix", "[Prefix]")
        return Message(
            id=msg.id,
            session_id=msg.session_id,
            from_instance=msg.from_instance,
            sender=msg.sender,
            ts=msg.ts,
            text=f"{prefix} {msg.text}" if msg.text else msg.text,
            raw=msg.raw,
        )
```
