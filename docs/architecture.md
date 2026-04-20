# Architecture

## Overview

Unigate is a **universal messaging exchange** - a message router that connects different communication channels. It receives messages, stores them durably, applies routing rules, and forwards them to destinations.

```
[Messenger A] ──────► [Unigate] ──────► [Messenger B]
                          │
                          ▼
                    [Your Handler]
```

## Core Components

### Exchange (Kernel)

The exchange is the heart of unigate. It handles:

1. **Receive** - Accept messages from channel instances
2. **Store** - Write messages to inbox durably
3. **Route** - Apply routing rules to determine destinations
4. **Forward** - Send messages to destination channels
5. **Retry** - Handle failures with retry policies

```
Message In → Dedup → Inbox → Route → Outbox → Send → Retry
```

### Instances

An instance is a named connection to one channel:

- Each instance has its own **inbox partition**
- Each instance has its own **outbox partition**
- Each instance has its own **credential storage**
- Instances are isolated - one failing doesn't affect others

### Channels

Channels are protocol implementations:

- **Telegram** - Bot API polling/webhook
- **WhatsApp** - Business API
- **Web** - Generic HTTP webhook
- **WebUI** - Built-in web interface
- **Internal** - In-process messaging

### Routing Engine

Routes messages based on YAML rules:

```yaml
routing:
  rules:
    - name: rule-name
      priority: 100
      match:
        from_instance: web
      actions:
        forward_to: [telegram]
```

Rules are evaluated by priority (lower = higher priority).

## Deployment Modes

### Standalone Mode

Run unigate as its own HTTP server:

```bash
unigate start
```

- HTTP server starts automatically
- All instances start automatically
- CLI connects via Unix socket

### Embedded Mode

Mount into existing ASGI app:

```python
from fastapi import FastAPI
from unigate import Unigate

app = FastAPI()
gate = Unigate.from_config("unigate.yaml")
gate.mount_to_app(app, prefix="/unigate")
```

- Routes added to parent app
- Instances NOT auto-started
- Start with CLI: `unigate start`

## Instance Lifecycle

```
unconfigured → setup_required → setting_up → active → degraded → reconnecting
                     ↑                                    ↓
                     └──────── credentials expired ←──────┘
```

| State | Description |
|-------|-------------|
| `unconfigured` | In config, not started |
| `setup_required` | Needs authentication |
| `setting_up` | Authenticating |
| `active` | Running normally |
| `degraded` | Circuit breaker open |
| `reconnecting` | Attempting to recover |

## Storage Model

**Message Stores** (4 stores with swappable backends):

| Store | Purpose | Backend Options |
|-------|---------|-----------------|
| Inbox | Received messages | Memory, SQLite, File |
| Outbox | Pending outbound | Memory, SQLite, File |
| Sessions | Conversation state | Memory, SQLite, File |
| Dedup | Idempotency | Memory, SQLite |

**Secure Store** (separate, for credentials/tokens):

| Store | Purpose | Backend Options |
|-------|---------|-----------------|
| SecureStore | API tokens, credentials | Memory, Encrypted SQLite |

Note: SecureStore is separate because it handles encrypted data (API keys, bot tokens) requiring different backend semantics.

### Backends

**Memory** - Fast, no persistence (dev/test)
**SQLite** - Single file, ACID transactions (production)
**File** - JSON files per message (debugging)
**Encrypted SQLite** - SQLite with encryption for secrets

## Resilience

### Retry Policy

Per-instance retry configuration:

```yaml
instances:
  my_channel:
    retry:
      max_attempts: 5
      base_delay_seconds: 2
      max_delay_seconds: 30
```

### Circuit Breaker

Prevents cascade failures:

```yaml
instances:
  my_channel:
    circuit_breaker:
      failure_threshold: 5
      recovery_timeout: 60
```

States: `closed` → `open` → `half_open` → `closed`

### Dead Letter Queue

Messages that exceed retry attempts go to dead letters:

```bash
unigate dead-letters list
unigate dead-letters requeue <id>
```

## Plugin System

### Plugin Types

| Type | Prefix | Example | Purpose |
|------|--------|---------|---------|
| Channel | `channel_` | `channel_telegram.py` | Receive/send messages |
| Matcher | `match_` | `match_text.py` | Match message conditions |
| Transform | `transform_` | `transform_truncate.py` | Modify messages |
| Transport | `transport_` | `transport_http.py` | Delivery methods |

### Registration

Plugins auto-register via:
1. Entry points in `pyproject.toml`
2. Files in `plugin_dirs` config
3. Direct import

### Creating a Channel

```python
from unigate import BaseChannel, ChannelCapabilities, SetupResult, Message

class MyChannel(BaseChannel):
    name = "mychannel"
    transport = "http"
    auth_method = "token"
    
    async def setup(self) -> SetupResult:
        # Authenticate
        return SetupResult.READY
    
    async def start(self) -> None:
        # Start polling/websocket
        pass
    
    async def stop(self) -> None:
        # Cleanup
        pass
    
    def to_message(self, raw: dict) -> Message:
        # Platform format → Message
        return Message(...)
    
    async def from_message(self, msg: Message) -> None:
        # Message → Platform format, send
        pass
    
    @property
    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(direction="bidirectional")
```

## Extensions

Extensions transform messages in the pipeline:

```python
class MyExtension(BaseExtension):
    name = "myext"
    priority = 10  # Lower = earlier
    
    async def process_inbound(self, msg: Message, ctx) -> Message | None:
        # Transform inbound
        msg.text = msg.text.upper()
        return msg
    
    async def process_outbound(self, msg: Message, ctx) -> Message | None:
        # Transform outbound
        return msg
```

## HTTP Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/status` | GET | Status dashboard |
| `/health` | GET | Health check |
| `/instances` | GET | Instance list |
| `/web/{name}` | GET | Web UI |
| `/webhook/{name}` | POST | Webhook receiver |

## CLI Architecture

Commands connect via:

1. **Unix Socket** - When daemon running
2. **Direct Import** - When no daemon

```bash
unigate start          # Start daemon
unigate stop           # Stop daemon
unigate status         # Check status
```

## Message Flow

```
1. Channel receives raw message
2. to_message() converts to Message
3. Message stored in Inbox
4. Routing rules evaluated
5. Matching rules trigger actions
6. Messages created for destinations
7. Messages stored in Outbox
8. Transport delivers message
9. Success → mark delivered
10. Failure → retry or dead letter
```

## Configuration

```yaml
unigate:
  mount_prefix: /unigate

storage:
  backend: memory
  path: ./unigate.db

instances:
  web:
    type: webui
    
  telegram:
    type: telegram
    token: !env:TELEGRAM_TOKEN

extensions:
  - name: identity
    config:
      auto_detect: true

routing:
  default_action: keep
  rules:
    - name: rule-name
      priority: 100
      match:
        from_instance: web
      actions:
        forward_to: [telegram]
```

## File Structure

```
unigate/
├── src/unigate/
│   ├── kernel.py          # Exchange core
│   ├── routing.py         # Routing engine
│   ├── instance_manager.py # Instance lifecycle
│   ├── lifecycle.py       # State machine
│   ├── stores.py          # Storage backends
│   ├── cli.py            # CLI commands
│   ├── runtime.py        # ASGI app
│   ├── gate.py           # Main entry point
│   ├── config.py         # Config loading
│   ├── plugins/
│   │   ├── base.py       # Registry
│   │   ├── channel_*.py  # Channel plugins
│   │   ├── match_*.py    # Matcher plugins
│   │   └── transform_*.py # Transform plugins
│   └── extensions.py     # Extension interfaces
├── tests/
└── docs/
```

## Future Extensions

### HTTP Management API
For embedded mode CLI support when Unix socket unavailable.

### Additional Channels
- Discord
- Slack
- Email (SMTP/IMAP)
- SMS (Twilio)

### Additional Features
- Metrics and tracing
- Configuration hot-reload
- Multi-tenant support
