# Architecture

Unigate is a universal messaging exchange with plugin-based channels and rule-based routing.

## Core Components

### Exchange Kernel

The `Exchange` manages message flow:

1. **Inbound**: receive -> dedup -> inbox -> routing/handler
2. **Outbound**: route -> outbox records -> send -> retry
3. **Lifecycle**: setup -> active -> degraded -> reconnecting

```
Message In → Deduplication → Inbox → Routing Engine → Rules → Outbox → Send
```

### Plugin Architecture

All plugins live in `src/unigate/plugins/` with flat structure:

| Type | Prefix | Example |
|------|--------|---------|
| Channel | `channel_` | `channel_telegram.py` → `channel.telegram` |
| Matcher | `match_` | `match_text.py` → `match.text_contains` |
| Transform | `transform_` | `transform_truncate.py` → `transform.truncate` |
| Transport | `transport_` | `transport_http.py` → `transport.http` |

### Plugin Registry

Central registry in `base.py`:

```python
class PluginRegistry:
    def register(self, cls: type, source: str = "builtin") -> None
    def enable(self, name: str) -> bool
    def disable(self, name: str) -> bool
    def get_channel(self, name: str) -> type | None
    def get_match(self, name: str) -> type | None
    def get_transform(self, name: str) -> type | None
    def get_transport(self, name: str) -> type | None
```

### Routing Engine

Rules are defined in YAML config:

```yaml
routing:
  default_action: keep  # keep, discard, or forward
  rules:
    - name: my-rule
      priority: 100      # lower = higher priority
      enabled: true
      match:
        from_instance: web_ui
        text_contains: "sales"
        sender_pattern: "vip_*"
      actions:
        forward_to: [telegram_bot]
        keep_in_default: true
        add_tags: [sales]
```

Match conditions:
- `from_instance` - Source channel instance
- `text_contains` - Text substring (case-insensitive)
- `text_pattern` - Regex pattern
- `sender_id` - Exact sender ID
- `sender_pattern` - Glob pattern for sender
- `group_id` - Exact group ID
- `has_media` - Media presence
- `day_of_week` - Day name (monday, tuesday, etc.)
- `hour_of_day` - Hour (0-23)

## Instance Lifecycle

Each channel instance has lifecycle states:

```
unconfigured → setup_required → setting_up → active → degraded → reconnecting
```

State transitions:
- `setup()` called → `setting_up`
- Setup success → `active`
- Health check fails → `degraded`
- Health recovers → `reconnecting` → `active`

## Sessions

Sessions are **instance-scoped** by default:

```
session_id = "{instance_id}:{sender_id}"
Example: "telegram_bot:+1234567890"
```

This means:
- Same user on SMS = session "sms:+1234567890"
- Same user on WhatsApp = session "whatsapp:+1234567890"
- Separate conversations per instance (simpler, more predictable)

### Cross-Platform Identity (Optional Extension)

To link users across platforms, use the **identity extension**:

```yaml
extensions:
  - name: identity
    config:
      identity_map:
        "+1234567890": alice  # Map phone to canonical ID
      auto_detect: true       # Auto-detect by phone pattern
```

The extension populates `sender.canonical_id`:
```python
if msg.sender.canonical_id == "alice":
    # Same user on any platform
```

Benefits:
- Core stays simple (no built-in cross-platform linking)
- Pluggable identity (phone, email, custom)
- Future-proof for new identity providers

## Storage Model

Five store roles:

| Store | Purpose | API |
|-------|---------|-----|
| inbox | Inbound messages | `put()`, `list_inbox()` |
| outbox | Outbound queue | `put()`, `mark_sent()`, `mark_failed()` |
| session | Origin resolution | `set_origin()`, `get_origin()` |
| dedup | Idempotency | `seen()`, `mark()` |
| secure | Credentials | `get()`, `set()` |

### Storage Backends

| Backend | Use Case | Command Line |
|---------|----------|--------------|
| `memory` | Testing, dev | Default |
| `sqlite` | Production, single instance | `--backend sqlite` |
| `file` | Debugging, easy backup | `--backend file` |

### Storage Configuration

Global defaults via CLI:
```bash
unigate start --backend sqlite --storage-path ~/.unigate/unigate.db --retention 14
```

Per-instance overrides via YAML config:
```yaml
storage:
  default: sqlite  # Global default backend
  default_path: ~/.unigate/unigate.db

instances:
  # Uses global default (sqlite)
  telegram_main:
    type: telegram
    
  # Custom file storage for debugging
  debug_bot:
    type: web
    storage:
      backend: file
      path: ./debug_data
      
  # Separate SQLite for high-volume instance
  high_volume:
    type: telegram
    storage:
      backend: sqlite
      path: ./data/high_volume.db
```

### FileStore Structure

Each message stored as JSON with rich metadata:
```json
{
  "type": "inbox",
  "namespace": "telegram_main",
  "message_id": "msg123",
  "instance_id": "telegram_main",
  "sender": {"id": "user456", "name": "John"},
  "received_at": "2024-01-01T12:00:00Z",
  "text": "Hello",
  "has_media": false,
  "raw": {...}
}
```

Directory structure:
```
~/.unigate/data/
├── inbox/
│   └── 20240101_120000_000000_telegram_inbox_msg123.json
├── outbox/
├── sent/
├── dead_letters/
├── sessions/
├── dedup/
└── interactions/
```

Built-in implementations:
- `InMemoryStores` - For testing, no persistence
- `SQLiteStores` - Single-file SQLite, fast queries
- `FileStores` - Human-readable JSON files, easy inspection

## Resilience

### Retry Policy

Per-instance configuration:

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
      half_open_max_requests: 1
```

States: `closed` → `open` → `half_open` → `closed`

### Dead Letter Queue

Messages that exceed retry attempts go to dead letters:

```
unigate dead-letters
```

## Runtime Interfaces

### Unified Serve Command

Start all configured instances with unified HTTP routing:

```bash
unigate serve --config unigate.yaml --port 8080
```

Routes:
- `GET /{prefix}/status` - Status dashboard with instance info and stats
- `GET /{prefix}/health` - Health check (for load balancers)
- `GET /{prefix}/instances` - List all instances with states
- `GET /{prefix}/web/{instance}` - Web UI for webui channels
- `POST /{prefix}/webhook/{instance}` - Webhook for other channels

### ASGI App

```python
from unigate import Unigate

gate = Unigate.from_config("unigate.yaml")
app = gate.create_server_app(port=8080)
```

Or mount to existing ASGI app:

```python
gate.mount_to_app(app, prefix="/unigate")
```

### CLI Commands

```bash
unigate serve --config my.yaml          # Start unified server
unigate plugins list                    # List plugins
unigate instances list                  # List instances
unigate inbox list                      # List inbox
unigate outbox list                     # List outbox
unigate dead-letters                   # View dead letters
```

## File Structure

```
unigate/
├── src/unigate/
│   ├── plugins/
│   │   ├── base.py           # Registry & protocols
│   │   ├── channel_*.py      # Channel plugins
│   │   ├── match_*.py        # Matcher plugins
│   │   ├── transform_*.py     # Transform plugins
│   │   └── transport_*.py     # Transport plugins
│   ├── routing.py            # Routing engine
│   ├── lifecycle.py          # Instance states
│   ├── instance_manager.py    # Lifecycle orchestration
│   ├── kernel.py             # Exchange kernel
│   ├── stores.py             # Storage backends
│   ├── channel.py            # BaseChannel contract
│   ├── message.py            # Message dataclass
│   ├── cli.py                # CLI commands
│   └── runtime.py            # ASGI runtime
├── tests/
│   ├── test_*.py             # Unit tests
│   └── test_routing_comprehensive.py
└── docs/
    ├── architecture.md
    └── plugin-development.md
```
