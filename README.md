# unigate

Transport-only messaging exchange for multi-channel systems.

Receives inbound payloads, deduplicates and stores them, routes handler output,
fans out per destination, retries failures, and exposes runtime operations through
ASGI routes and CLI commands.

## Installation

```powershell
# Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install in development mode
pip install -e .

# Run tests
PYTHONPATH=src python -m unittest discover -s tests -v
```

Or with dev dependencies (linting, type checking):

```powershell
pip install -e ".[dev]"
```

## Quick Start

```python
from unigate import Unigate, Message

gate = Unigate.from_config("unigate.yaml")

@gate.on_message
async def handle(msg: Message) -> Message:
    return Message(
        to=[],
        session_id=msg.session_id,
        from_instance="handler",
        sender=msg.sender,
        ts=msg.ts,
        text=f"got: {msg.text}"
    )

# Run with ASGI server (uvicorn, hypercorn, etc.)
gate.serve()
```

## Architecture

- **one universal `Message`** for both directions
- **adapter boundary (`BaseChannel`)** for translation and capability degradation
- **exchange pipelines** for inbound and outbound message flow
- **lifecycle-aware instances** with setup and health transitions
- **extension chain** for inbound/outbound/event hooks
- **durable stores**: `InMemoryStores`, `SQLiteStores`

## CLI Commands

```powershell
unigate serve                    # Start kernel (use with ASGI server)
unigate start                   # Start daemon in background
unigate stop                    # Stop daemon
unigate status                  # Show status
unigate instances list           # List all instances
unigate instances status <name> # Instance details
unigate inbox list              # List inbox records
unigate outbox list             # List outbox records
unigate outbox retry            # Retry failed messages
unigate outbox dead-letters     # View dead letters
```

## Channels

### Telegram

Two modes:

1. **polling** (default, good for development):
   - Long polling with 55-second timeout
   - No external URL needed
   - Efficient - only requests when updates available

2. **webhook** (better for production):
   - Telegram pushes updates to your URL
   - Requires public HTTPS endpoint
   - Lower latency, higher efficiency

```yaml
instances:
  my_bot:
    type: telegram
    token: !env:TELEGRAM_BOT_TOKEN
    mode: polling  # or webhook

  # Multiple Telegram bots:
  support_bot:
    type: telegram
    token: !env:SUPPORT_BOT_TOKEN
    mode: polling

  sales_bot:
    type: telegram  
    token: !env:SALES_BOT_TOKEN
    mode: webhook
    webhook_url: https://yourdomain.com/unigate/webhook/sales_bot
    webhook_secret: your-secret
```

### Web

Generic HTTP webhook with multiple auth methods:

```yaml
instances:
  api_channel:
    type: web
    auth_method: api_key
    api_key: !env:API_KEY
```

### Internal

In-process messaging for testing or internal use:

```yaml
instances:
  internal:
    type: internal
```

## Configuration (unigate.yaml)

```yaml
unigate:
  mount_prefix: /unigate
  max_concurrent_processing: 50

storage:
  backend: sqlite  # or: memory, redis
  path: ./unigate.db

deduplication:
  window_seconds: 300

instances:
  my_telegram:
    type: telegram
    token: !env:TELEGRAM_BOT_TOKEN
    mode: polling
    retry:
      max_attempts: 5
      base_delay_seconds: 2
      max_delay_seconds: 30
    circuit_breaker:
      failure_threshold: 5
      recovery_timeout: 60
```

## Multiple Instances

Each instance has its own:
- Auth credentials (stored securely per-instance)
- Retry policy
- Circuit breaker
- Outbox queue

Example - Telegram with different bots:

```yaml
instances:
  bot_alpha:
    type: telegram
    token: !env:BOT_ALPHA_TOKEN
  
  bot_beta:
    type: telegram
    token: !env:BOT_BETA_TOKEN
```

Messages to bot_alpha stay isolated from bot_beta.

## Development

```powershell
# Lint
ruff check src/

# Type check
mypy src/ --strict
```

## Documentation

- [Architecture](docs/architecture.md)
- [Roadmap](docs/roadmap.md)
- [Contributing](CONTRIBUTING.md)
