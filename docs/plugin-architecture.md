# Unified Plugin Architecture

## Overview

Unigate uses a **plugin-based architecture** for extensibility. Plugins are reusable components discovered at runtime. User configuration (routing rules, instance settings) lives outside plugins and references them by name.

---

## Plugin Types

| Type | Description | Location | Base Class |
|------|-------------|----------|------------|
| `channel` | Receive/send messages | Built-in + user `plugins/channels/` | `BaseChannel` |
| `transform` | Modify message content | `plugins/transforms/` | `TransformExtension` |
| `transport` | Push to external services | `plugins/transports/` | `TransportProtocol` |
| `matcher` | Routing condition logic | `plugins/matchers/` | `RoutingMatcher` |

**Routing rules** = User config, NOT plugins.

---

## Plugin Discovery

### Built-in Plugins

Ship with unigate:
- `channels/web.py` - Generic HTTP webhook
- `channels/telegram.py` - Telegram Bot API
- `channels/webui.py` - Web UI testing interface

### User Plugins

Users specify plugin directories in config:

```yaml
unigate:
  plugin_dirs:
    channels: ./plugins/channels
    transforms: ./plugins/transforms
    transports: ./plugins/transports
    matchers: ./plugins/matchers
```

---

## Channel Plugin

### Purpose
Receive and send messages to/from external platforms.

### Base Class
```python
# src/unigate/channel.py
class BaseChannel(ABC):
    name: str
    transport: str
    auth_method: str
    
    async def setup(self) -> SetupResult: ...
    async def to_message(self, raw: dict) -> Message: ...
    async def from_message(self, msg: Message) -> dict: ...
```

### Example
```python
# plugins/channels/whatsapp.py
from unigate import BaseChannel

class WhatsAppChannel(BaseChannel):
    name = "whatsapp"
    transport = "rest_api"
    auth_method = "bearer"
    
    async def setup(self):
        return SetupResult(status=SetupStatus.READY)
    
    async def to_message(self, raw):
        # Convert WhatsApp webhook payload to Message
        ...
```

---

## Transform Plugin

### Purpose
Modify message content before routing/delivery.

### Base Class
```python
# src/unigate/extensions.py
class TransformExtension(Protocol):
    name: str
    
    async def transform(self, msg: Message, config: dict) -> Message:
        """Transform message. Return modified message."""
        ...
```

### Example
```python
# plugins/transforms/truncate_160.py
from unigate import Message, TransformExtension

class Truncate160Transform(TransformExtension):
    name = "truncate_160"
    
    async def transform(self, msg: Message, config: dict) -> Message:
        max_len = config.get("max_length", 160)
        if msg.text and len(msg.text) > max_len:
            msg.text = msg.text[:max_len-3] + "..."
        return msg
```

### Config Usage
```yaml
extensions:
  - name: truncate_160
    module: plugins.transforms.truncate_160
    config:
      max_length: 160

routing:
  rules:
    - name: sms_alert
      match:
        from_channel: whatsapp
      actions:
        transforms:
          - truncate_160
        forward_to:
          - sms
```

---

## Transport Plugin

### Purpose
Define HOW to deliver messages to destinations (beyond just calling channel.send).

### Base Class
```python
# src/unigate/transports/base.py
class TransportProtocol(Protocol):
    name: str
    async def send(self, msg: Message, config: dict) -> bool: ...
```

### Built-in Transports

```python
# src/unigate/transports/
├── __init__.py
├── http.py      # HTTP POST/GET webhook
├── ftp.py       # FTP upload
├── websocket.py # WebSocket push
├── sftp.py      # Secure FTP
├── email.py     # SMTP email send
└── sms.py       # SMS API (Twilio, etc.)
```

### Example: FTP Transport
```python
# plugins/transports/ftp_push.py
from unigate import Message
from unigate.transports.base import TransportProtocol

class FTPTransport(TransportProtocol):
    name = "ftp_push"
    
    async def send(self, msg: Message, config: dict) -> bool:
        host = config["host"]
        username = config["username"]
        password = config["password"]
        path = config.get("path", "/")
        
        # Upload msg.text or msg.media to FTP
        ...
        return True
```

### Config Usage
```yaml
transports:
  - name: ftp_push
    module: plugins.transports.ftp_push
    config:
      host: ftp.example.com
      username: !env:FTP_USER
      password: !env:FTP_PASS
      path: /uploads

instances:
  ftp_archive:
    type: transport
    transport: ftp_push
    config:
      path: /archive

routing:
  rules:
    - name: archive_to_ftp
      match:
        from_channel: email
        has_attachment: true
      actions:
        forward_to:
          - ftp_archive
```

---

## Matcher Plugin

### Purpose
Extensible conditions for routing rule matching.

### Base Class
```python
# src/unigate/routing/matchers/base.py
class RoutingMatcher(Protocol):
    name: str  # e.g., "from_channel", "text_contains", "has_attachment"
    
    def match(self, msg: Message, value: Any) -> bool:
        """Return True if message matches condition."""
        ...
```

### Built-in Matchers

| Matcher | Config Key | Example |
|---------|------------|---------|
| `channel_matcher` | `from_channel` | `from_channel: telegram` |
| `sender_matcher` | `sender_pattern` | `sender_pattern: "*@company.com"` |
| `text_matcher` | `text_contains`, `text_pattern` | `text_contains: "help"` |
| `subject_matcher` | `subject_contains` | `subject_contains: "URGENT"` |
| `context_matcher` | `group_id`, `thread_id` | `group_id_pattern: "support-*"` |
| `media_matcher` | `has_media`, `has_attachment` | `has_attachment: true` |
| `time_matcher` | `day_of_week`, `hour_of_day` | `hour_of_day: 9-17` |
| `metadata_matcher` | `metadata.key` | `metadata.priority: high` |

### Example: Custom Matcher
```python
# plugins/matchers/day_of_week.py
from datetime import datetime
from unigate import Message
from unigate.routing.matchers.base import RoutingMatcher

class DayOfWeekMatcher(RoutingMatcher):
    name = "day_of_week"
    
    def match(self, msg: Message, value: str | list[str]) -> bool:
        days = value if isinstance(value, list) else [value]
        current_day = msg.ts.strftime("%A").lower()
        return current_day in [d.lower() for d in days]
```

### Config Usage
```yaml
routing:
  rules:
    - name: business_hours
      match:
        day_of_week: [monday, tuesday, wednesday, thursday, friday]
        hour_of_day: 9-17
      actions:
        forward_to:
          - support_team
```

---

## Routing Rules = Config (Not Plugins)

### Location
User-defined. Not in plugins folder.

### Recommended Structure
```
my_app/
├── unigate.yaml              # Main config
├── config/
│   └── routing/
│       ├── default.yaml      # Default routing rules
│       ├── production.yaml   # Production overrides
│       └── test.yaml         # Test rules
└── plugins/                  # Plugin code
    ├── channels/
    ├── transforms/
    ├── transports/
    └── matchers/
```

### Example Config
```yaml
# unigate.yaml
unigate:
  plugin_dirs:
    channels: ./plugins/channels
    transforms: ./plugins/transforms
    transports: ./plugins/transports
    matchers: ./plugins/matchers
  default_instance: inbox

instances:
  telegram:
    type: channel
    channel: telegram
    token: !env:TELEGRAM_TOKEN
  
  email_in:
    type: channel
    channel: web
    auth: bearer
  
  handler:
    type: handler
  
  inbox:
    type: internal

routing:
  rules_file: ./config/routing/default.yaml

extensions:
  - name: truncate_160
    module: plugins.transforms.truncate_160
  - name: extract_subject
    module: plugins.transforms.extract_subject
```

```yaml
# config/routing/default.yaml
rules:
  - name: email_to_telegram
    priority: 100
    match:
      from_channel: email_in
      subject_contains: "urgent"
    actions:
      transforms:
        - extract_subject
      forward_to:
        - telegram
        - handler

  - name: all_to_handler
    priority: 1000
    match: {}  # Match everything
    actions:
      forward_to:
        - handler
```

---

## File Structure

```
unigate/
├── src/unigate/
│   ├── __init__.py
│   ├── channel.py              # BaseChannel
│   ├── channels/               # Built-in channels
│   │   ├── __init__.py
│   │   ├── web.py
│   │   ├── telegram.py
│   │   └── webui.py
│   │
│   ├── extensions.py            # Extension protocols (Inbound, Outbound, Event)
│   ├── transforms/              # Built-in transforms
│   │   ├── __init__.py
│   │   ├── base.py              # TransformExtension base
│   │   ├── truncate.py
│   │   ├── extract_subject.py
│   │   └── add_metadata.py
│   │
│   ├── transports/              # Built-in transports
│   │   ├── __init__.py
│   │   ├── base.py              # TransportProtocol
│   │   ├── http.py
│   │   ├── ftp.py
│   │   ├── websocket.py
│   │   ├── email.py
│   │   └── sms.py
│   │
│   ├── routing/
│   │   ├── __init__.py
│   │   ├── engine.py            # RoutingEngine
│   │   ├── rule.py              # Rule definition
│   │   ├── matchers/            # Built-in matchers
│   │   │   ├── __init__.py
│   │   │   ├── base.py          # RoutingMatcher base
│   │   │   ├── channel.py
│   │   │   ├── sender.py
│   │   │   ├── text.py
│   │   │   ├── subject.py
│   │   │   ├── context.py
│   │   │   ├── media.py
│   │   │   └── time.py
│   │   └── loader.py            # Load rules from config
│   │
│   ├── registry.py              # Plugin discovery
│   └── ...
│
├── plugins/                     # Example user plugins (in examples/)
│   ├── channels/
│   ├── transforms/
│   ├── transports/
│   └── matchers/
│
├── examples/
│   └── unigate.yaml.example
│
├── config/                      # Example routing configs
│   └── routing/
│       └── default.yaml.example
│
└── docs/
    └── plugin-architecture.md
```

---

## Implementation Checklist

### Phase 1: Core Plugin System
- [x] `BaseChannel` and channel registry
- [x] Plugin discovery via `plugin_dirs`
- [x] Entry point loading

### Phase 2: Transform Plugins
- [ ] `TransformExtension` base class
- [ ] Built-in transforms (truncate, extract_subject, add_metadata)
- [ ] Config-based transform loading

### Phase 3: Transport Plugins
- [ ] `TransportProtocol` base class
- [ ] Built-in transports (HTTP, FTP, WebSocket, Email, SMS)
- [ ] Instance type: `transport`

### Phase 4: Matcher Plugins
- [ ] `RoutingMatcher` base class
- [ ] Built-in matchers (channel, sender, text, subject, context, media, time)
- [ ] Matcher registry
- [ ] Custom matcher support

### Phase 5: Routing Engine Integration
- [x] Routing engine with rule evaluation
- [ ] Integration with transforms
- [ ] Integration with transports
- [ ] Integration with matchers
- [ ] `rules_file` loading

### Phase 6: Documentation & Examples
- [ ] Update docs/plugin-architecture.md
- [ ] Example plugins in `examples/plugins/`
- [ ] Example routing configs in `examples/config/`

---

## Backward Compatibility

Existing config format still works:

```yaml
instances:
  telegram:
    type: telegram
    token: !env:TELEGRAM_TOKEN
```

Becomes:

```yaml
instances:
  telegram:
    type: channel
    channel: telegram
    token: !env:TELEGRAM_TOKEN
```

Both formats supported initially, deprecate old format in v0.3.0.
