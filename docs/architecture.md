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

## Storage Model

Five store roles:

| Store | Purpose | API |
|-------|---------|-----|
| inbox | Inbound messages | `put()`, `list_inbox()` |
| outbox | Outbound queue | `put()`, `mark_sent()`, `mark_failed()` |
| session | Origin resolution | `set_origin()`, `get_origin()` |
| dedup | Idempotency | `seen()`, `mark()` |
| secure | Credentials | `get()`, `set()` |

Built-in implementations:
- `InMemoryStores` - For testing
- `SQLiteStores` - For persistence

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

### ASGI App

```python
from unigate.runtime import UnigateASGIApp

app = UnigateASGIApp(exchange, mount_prefix="/unigate")
```

Routes:
- `GET /{prefix}/status` - Instance status
- `GET /{prefix}/health` - Health check
- `POST /{prefix}/webhook/{instance}` - Webhook receiver

### CLI Commands

```bash
unigate plugins list          # List plugins
unigate instances list        # List instances
unigate inbox list           # List inbox
unigate outbox list          # List outbox
unigate dead-letters         # View dead letters
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
