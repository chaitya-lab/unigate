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
unigate status                  # Kernel health and stats
unigate instances list           # List all instances
unigate instances status <name> # Instance details
unigate inbox list              # List inbox records
unigate outbox list             # List outbox records
unigate outbox retry            # Retry failed messages
unigate outbox dead-letters     # View dead letters
```

## Channels

Built-in adapters:

- `internal` - In-process messaging
- `web` - Generic HTTP webhook with HMAC/Bearer/API Key auth
- `telegram` - Telegram Bot API

## Configuration (unigate.yaml)

```yaml
unigate:
  mount_prefix: /unigate
  max_concurrent_processing: 50

storage:
  backend: sqlite
  path: ./unigate.db

instances:
  my_bot:
    type: telegram
    token: !env:TELEGRAM_BOT_TOKEN
    mode: polling
```

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
