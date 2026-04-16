# Unified Plugin System

## Overview

Unigate uses a **flat plugin structure** with naming conventions. Each plugin file can contain one or more plugins of any type. The system auto-discovers plugins from configured directories.

---

## Plugin Types

All plugins operate on the **universal Message format**. Channels convert raw external data → Message. Matchers, transforms, and transports work with Message.

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
├── __init__.py
├── message.py           # Universal message format
├── channel.py           # BaseChannel (for channels)
├── plugins/             # All plugin files (flat structure)
│   ├── __init__.py
│   ├── channel_web.py
│   ├── channel_telegram.py
│   ├── channel_whatsapp.py
│   ├── match_from.py
│   ├── match_text.py
│   ├── match_sender.py
│   ├── match_media.py
│   ├── match_time.py
│   ├── transform_truncate.py
│   ├── transform_extract.py
│   ├── transform_add.py
│   ├── transport_http.py
│   ├── transport_ftp.py
│   └── transport_ws.py
└── ...
```

**User plugins directory:**
```
my_app/
├── plugins/             # Flat structure, naming convention
│   ├── channel_whatsapp.py
│   ├── match_myrule.py
│   └── transform_special.py
└── unigate.yaml
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

## Auto-Discovery

Plugins are auto-discovered from configured directories:

```yaml
unigate:
  plugin_dirs:
    - ./plugins
    - ./custom_plugins
```

Discovery process:
1. Scan each directory for `*.py` files
2. Import each module
3. Find classes inheriting from plugin base types
4. Register by `name` attribute

---

## Routing Rules (Config, Not Plugins)

Routing rules reference plugins by name:

```yaml
# unigate.yaml
routing:
  rules:
    - name: urgent_to_sms
      match:
        from: telegram
        text_contains: URGENT
      transform:
        - truncate_160
      forward_to:
        - sms_channel
        - handler
```

```yaml
# Custom routing rules file
rules:
  - name: whatsapp_attach_to_ftp
    match:
      from: whatsapp
      has_attachment: true
    transform:
      - whatsapp_save_attachment
    forward_to:
      - ftp_archive
```

---

## Built-in Plugins

### Channels
| Plugin | File | Description |
|--------|------|-------------|
| web | `channel_web.py` | HTTP webhook receiver |
| telegram | `channel_telegram.py` | Telegram Bot API |
| webui | `channel_webui.py` | Web UI for testing |

### Matchers
| Plugin | File | Description |
|--------|------|-------------|
| from | `match_from.py` | Match by source channel |
| sender | `match_sender.py` | Match by sender ID/pattern |
| text_contains | `match_text.py` | Match text content |
| subject_contains | `match_text.py` | Match email subject |
| has_media | `match_media.py` | Match by media presence |
| day_of_week | `match_time.py` | Match by day/time |

### Transforms
| Plugin | File | Description |
|--------|------|-------------|
| truncate | `transform_truncate.py` | Truncate text length |
| extract_subject | `transform_extract.py` | Extract email subject |
| add_metadata | `transform_add.py` | Add metadata fields |

### Transports
| Plugin | File | Description |
|--------|------|-------------|
| http | `transport_http.py` | HTTP webhook push |
| ftp | `transport_ftp.py` | FTP/SFTP upload |
| websocket | `transport_ws.py` | WebSocket push |

---

## Example: Creating a Custom Channel

```python
# plugins/channel_mychannel.py
from unigate import Message, Sender, ChannelPlugin
from datetime import datetime, timezone

class MyChannelPlugin(ChannelPlugin):
    name = "mychannel"
    
    async def receive(self, raw: dict) -> Message | None:
        if raw.get("event") != "message":
            return None
        
        return Message(
            id=raw["message_id"],
            session_id=raw.get("session_id", raw["user_id"]),
            from_instance=self.name,
            sender=Sender(
                platform_id=raw["user_id"],
                name=raw.get("user_name", "User"),
            ),
            ts=datetime.now(timezone.utc),
            text=raw.get("text", ""),
        )
    
    async def send(self, msg: Message) -> dict | None:
        return {
            "user_id": msg.to[0] if msg.to else None,
            "text": msg.text,
        }
```

---

## Example: Creating a Custom Transform

```python
# plugins/transform_company_prefix.py
from unigate import Message, TransformPlugin

class CompanyPrefixTransform(TransformPlugin):
    name = "company_prefix"
    
    async def transform(self, msg: Message, config: dict) -> Message:
        prefix = config.get("prefix", "[Company]")
        if msg.text:
            msg.text = f"{prefix} {msg.text}"
        return msg
```

---

## Example: Creating a Custom Matcher

```python
# plugins/match_priority.py
from unigate import Message, MatcherPlugin

class PriorityMatcher(MatcherPlugin):
    name = "priority"
    
    def match(self, msg: Message, value: str) -> bool:
        return msg.metadata.get("priority") == value
```

Config usage:
```yaml
rules:
  - name: high_priority
    match:
      priority: high
    forward_to:
      - pagerduty
```

---

## Installation

### Built-in plugins
Included with unigate, auto-loaded.

### Custom plugins
1. Create files in your plugins directory
2. Register directory in config:
```yaml
unigate:
  plugin_dirs:
    - ./plugins
```

### Distribution (pip)
Create a package:
```
my-unigate-plugins/
├── my_unigate_plugins/
│   ├── __init__.py
│   ├── channel_slack.py
│   └── match_slack.py
└── setup.py
```

Install and use:
```yaml
unigate:
  plugin_dirs:
    - my_unigate_plugins/
```
