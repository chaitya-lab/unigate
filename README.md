# Unigate

**Universal messaging exchange with plugin-based channels and rule-based routing.**

Receive messages from any channel, apply routing rules, and forward to destinations with retry logic and circuit breakers.

---

## What is Unigate?

Unigate is a **messaging exchange** - like a postal system for software:

```
[Channel A] ────► [Unigate Exchange] ────► [Channel B]
                       │
                       ▼
                 [Your Handler]
```

- Receives messages from any channel (Telegram, WhatsApp, Web, etc.)
- Stores them durably
- Applies routing rules
- Forwards to correct destinations
- Handles failures with retries and circuit breakers

---

## Quick Start

```bash
# Install
pip install -e .

# Create config
echo 'unigate:
  mount_prefix: /unigate
instances:
  web:
    type: webui
routing:
  default_action: keep' > unigate.yaml

# Start server
unigate start

# Open Web UI
# http://localhost:8080/unigate/web/web/
```

---

## Two Ways to Use

### Standalone Mode
Run unigate as its own server:

```bash
unigate start --config unigate.yaml
```

### Embedded Mode
Mount into existing app:

```python
from fastapi import FastAPI
from unigate import Unigate

app = FastAPI()
gate = Unigate.from_config("unigate.yaml")
gate.mount_to_app(app, prefix="/unigate")
# Start with: unigate start --config unigate.yaml
```

---

## Features

| Feature | Description |
|---------|-------------|
| **Channels** | Telegram, WhatsApp, Web, WebUI, and more |
| **Routing** | Rule-based routing with YAML config |
| **Resilience** | Retry, circuit breaker, dead letters |
| **Plugins** | Extend with custom channels, matchers, transforms |
| **CLI** | Full management interface |

---

## Channels

Connect to messaging platforms:

- **Telegram** - Bot API with polling
- **WhatsApp** - Business API
- **Web** - Generic HTTP webhook
- **WebUI** - Built-in web interface

---

## Configuration

```yaml
unigate:
  mount_prefix: /unigate

instances:
  web:
    type: webui

  telegram:
    type: telegram
    token: !env:TELEGRAM_TOKEN

routing:
  default_action: keep
  rules:
    - name: web-to-telegram
      priority: 100
      match:
        from_instance: web
      actions:
        forward_to: [telegram]
```

---

## CLI Commands

```bash
# Server
unigate start                    # Start server
unigate stop                     # Stop server

# Instances
unigate instances list           # List instances
unigate instances enable <id>   # Enable
unigate instances disable <id>  # Disable

# Messages
unigate inbox list              # View inbox
unigate outbox list             # View outbox
unigate dead-letters            # View failures
```

---

## HTTP Routes

| Route | Description |
|-------|-------------|
| `GET /unigate/status` | Status dashboard |
| `GET /unigate/health` | Health check |
| `GET /unigate/instances` | Instance list |
| `GET /unigate/web/{name}` | Web UI |
| `POST /unigate/webhook/{name}` | Webhook |

---

## Documentation

| Document | Description |
|----------|-------------|
| [Getting Started](docs/getting-started.md) | Step-by-step tutorials |
| [Configuration](docs/configuration.md) | Complete config reference |
| [CLI Reference](docs/cli.md) | All CLI commands |
| [Routing](docs/routing.md) | Routing rules |
| [Plugins](docs/plugins.md) | Create custom plugins |
| [Architecture](docs/architecture.md) | System design |

---

## Installation

```bash
git clone <repo>
cd unigate
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\Activate.ps1 on Windows
pip install -e ".[dev]"
python -m pytest tests/ -v
```

---

## License

MIT
