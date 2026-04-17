# Unigate

**Universal messaging exchange with plugin-based channels and rule-based routing.**

Receive messages from any channel, apply routing rules, and forward to destinations with retry logic and circuit breakers.

---

## What is Unigate?

Unigate is a **messaging exchange** - like a postal system for software. It:
- Receives messages from any channel (Telegram, WhatsApp, Web, etc.)
- Stores them durably
- Applies routing rules
- Forwards to correct destinations
- Handles failures with retries and circuit breakers

**Mental model:**
```
[Channel A] ---inbound---> [Unigate Exchange] ---outbound---> [Channel B]
     |                           |
     |                           +---> [Handler/Agent]
     |                           |
     +---reply-------------------+
```

---

## Two Ways to Use

### Standalone Mode
Run unigate as its own HTTP server with all instances.

```powershell
unigate start
# Server runs at http://localhost:8080/unigate/
```

### Embedded Mode
Mount unigate into an existing ASGI app (FastAPI, etc.).

```python
from fastapi import FastAPI
from unigate import Unigate

app = FastAPI()
gate = Unigate.from_config("unigate.yaml")
gate.mount_to_app(app, prefix="/messages")

# Run app: uvicorn main:app --port 8000
# Start instances: unigate start --config unigate.yaml
```

---

## Features

### Channels
Connect to any messaging platform:
- **Telegram** - Bot API with polling
- **WhatsApp** - Business API
- **Web** - Generic HTTP webhook
- **WebUI** - Built-in web interface for testing

### Routing
Rule-based message routing with YAML config:
- Route by sender, content, group, time, etc.
- Forward to single or multiple destinations
- Transform messages before delivery

### Resilience
- **Retry** - Automatic retry with exponential backoff
- **Circuit Breaker** - Prevent cascade failures
- **Dead Letter Queue** - Failed messages for manual review
- **Deduplication** - Prevent duplicate message processing

### Extensibility
- **Plugins** - Add new channels, matchers, transforms
- **Extensions** - Transform messages inbound/outbound
- **Transports** - HTTP, WebSocket, FTP, File

---

## Quick Start

### 1. Install

```powershell
git clone <repo>
cd unigate
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

### 2. Create Config

```yaml
# unigate.yaml
unigate:
  mount_prefix: /unigate

instances:
  web:
    type: webui

routing:
  default_action: keep
```

### 3. Start Server

```powershell
unigate start
# Opens: http://localhost:8080/unigate/web/web/
```

### 4. Send a Message

Open the Web UI and type a message. Add a handler for responses.

---

## Configuration

### Basic Config

```yaml
unigate:
  mount_prefix: /unigate

storage:
  backend: memory  # memory | sqlite | file

instances:
  web:
    type: webui

  telegram_bot:
    type: telegram
    token: !env:TELEGRAM_BOT_TOKEN
```

### Instances

Each instance is a named connection to a channel:

```yaml
instances:
  my_web:
    type: webui
    
  sales_telegram:
    type: telegram
    token: !env:TELEGRAM_TOKEN
    mode: polling  # polling | webhook
```

### Routing Rules

Route messages based on conditions:

```yaml
routing:
  default_action: keep  # keep | discard
  
  rules:
    # Forward web messages to Telegram
    - name: web-to-telegram
      priority: 100
      match:
        from_instance: web
      actions:
        forward_to: [telegram_bot]
    
    # Forward messages containing "help"
    - name: help-desk
      priority: 50
      match:
        text_contains: "help"
      actions:
        forward_to: [support_telegram]
```

### Match Conditions

| Condition | Example | Description |
|-----------|---------|-------------|
| `from_instance` | `web` | Match source channel |
| `text_contains` | `"sales"` | Match text content |
| `text_pattern` | `"^/cmd.*"` | Regex pattern |
| `sender` | `"user123"` | Exact sender ID |
| `sender_pattern` | `"vip_*"` | Glob pattern |
| `group_id` | `"support"` | Group ID |
| `has_media` | `true` | Has attachments |
| `day_of_week` | `["monday", "friday"]` | Days |
| `hour_of_day` | `[9, 10, 11, 12, 13, 14, 15, 16, 17]` | Hours |

### Actions

```yaml
actions:
  forward_to: [telegram_bot]    # Forward to destinations
  keep_in_default: true           # Keep in source too
  add_tags: [urgent]             # Tag the message
```

---

## CLI Commands

```powershell
# Server
unigate start                    # Start (background)
unigate start -f               # Start (foreground)
unigate start --port 9000       # Custom port
unigate stop                    # Stop server

# Instances
unigate instances list           # List all instances
unigate instances status         # Detailed status
unigate instances enable <id>   # Enable instance
unigate instances disable <id>  # Disable instance

# Messages
unigate inbox list              # List received messages
unigate inbox show <id>         # Show message
unigate inbox replay <id>       # Replay message

unigate outbox list             # List pending messages
unigate outbox retry            # Retry failed

unigate dead-letters            # View failed messages

# Plugins
unigate plugins list            # List plugins
unigate plugins enable <name>   # Enable plugin
unigate plugins disable <name>  # Disable plugin

# System
unigate status                  # Server status
unigate health                  # Health check
unigate logs                    # View logs
```

---

## HTTP Routes

When unigate is running, these routes are available:

| Route | Description |
|-------|-------------|
| `GET /{prefix}/status` | Status dashboard |
| `GET /{prefix}/health` | Health check |
| `GET /{prefix}/instances` | Instance list |
| `GET /{prefix}/web/{name}` | Web UI |
| `POST /{prefix}/webhook/{name}` | Webhook |

---

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────┐
│                      Unigate                            │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────┐     ┌─────────────┐                   │
│  │  Channel A  │     │  Channel B  │     Channels       │
│  │  (Telegram) │     │   (WebUI)  │                   │
│  └──────┬──────┘     └──────┬──────┘                   │
│         │                    │                          │
│         ▼                    ▼                          │
│  ┌─────────────────────────────────────┐                │
│  │          Exchange Kernel             │   Core         │
│  │  - Receive messages                  │                │
│  │  - Store durably (inbox/outbox)      │                │
│  │  - Route to destinations              │                │
│  │  - Retry failed deliveries             │                │
│  └─────────────────────────────────────┘                │
│                      │                                   │
│                      ▼                                   │
│  ┌─────────────────────────────────────┐                │
│  │        Routing Engine                 │   Routing      │
│  │  - Evaluate rules by priority        │                │
│  │  - Transform messages                 │                │
│  │  - Determine destinations             │                │
│  └─────────────────────────────────────┘                │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Instance Lifecycle

```
unconfigured → setup_required → setting_up → active → degraded → reconnecting
```

- **unconfigured** - In config, not started
- **setup_required** - Needs authentication
- **setting_up** - Authenticating
- **active** - Running normally
- **degraded** - Circuit breaker open or health check failing
- **reconnecting** - Attempting to reconnect

### Storage

| Store | Purpose |
|-------|---------|
| Inbox | Received messages |
| Outbox | Pending outbound messages |
| Sessions | Conversation state |
| Dedup | Duplicate detection |
| SecureStore | Encrypted credentials |

Backends: **Memory** (dev), **SQLite** (production), **File** (debug)

---

## Plugins

### Plugin Types

| Type | Prefix | Example |
|------|--------|---------|
| Channel | `channel_` | `channel_telegram.py` |
| Matcher | `match_` | `match_text.py` |
| Transform | `transform_` | `transform_truncate.py` |
| Transport | `transport_` | `transport_http.py` |

### Available Plugins

**Channels:**
- `channel.web` - Generic HTTP webhook
- `channel.webui` - Built-in web UI
- `channel.telegram` - Telegram Bot API
- `channel.whatsapp` - WhatsApp Business API

**Matchers:**
- `match.text_contains` - Match text content
- `match.text_pattern` - Regex match
- `match.sender` - Match sender ID
- `match.from` - Match source instance
- `match.has_media` - Match attachments
- `match.day_of_week` - Match day
- `match.hour_of_day` - Match hour

**Transforms:**
- `transform.truncate` - Truncate text
- `transform.extract_subject` - Extract email subject
- `transform.add_metadata` - Add metadata

**Transports:**
- `transport.http` - HTTP POST
- `transport.websocket` - WebSocket
- `transport.ftp` - FTP upload
- `transport.file` - File output

---

## Development

### Run Tests

```powershell
python -m pytest tests/ -v
```

### Create a Channel Plugin

```python
# my_channels/hello.py
from unigate import BaseChannel, ChannelCapabilities, SetupResult, Message

class HelloChannel(BaseChannel):
    name = "hello"
    transport = "stdio"
    auth_method = "none"
    
    async def setup(self) -> SetupResult:
        return SetupResult.READY
    
    async def start(self) -> None:
        print("Hello channel started!")
    
    async def stop(self) -> None:
        print("Hello channel stopped!")
    
    def to_message(self, raw: dict) -> Message:
        return Message(
            id=raw["id"],
            from_instance=self.instance_id,
            sender={"id": "console", "name": "User"},
            text=raw.get("text", ""),
        )
    
    async def from_message(self, msg: Message) -> None:
        print(f"Response: {msg.text}")
    
    @property
    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(direction="bidirectional")
```

Add to config:
```yaml
instances:
  hello:
    type: hello
```

---

## Documentation

- [docs/architecture.md](docs/architecture.md) - System design
- [docs/routing.md](docs/routing.md) - Routing rules reference
- [docs/plugin-development.md](docs/plugin-development.md) - Create plugins
- [docs/plugin-architecture.md](docs/plugin-architecture.md) - Plugin system

---

## License

MIT
