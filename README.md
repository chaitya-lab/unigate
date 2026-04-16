# Unigate

**Universal messaging exchange with plugin-based channels and rule-based routing.**

Receive messages from any channel, apply routing rules, and forward to destinations with retry logic and circuit breakers.

## Features

- **Plugin Architecture** - Flat structure with type-prefixed plugins (`channel.telegram`, `match.text_contains`, `transform.truncate`, `transport.http`)
- **Rule-Based Routing** - YAML configuration for routing based on sender, content, group, time, etc.
- **Channel Lifecycle** - Instances support setup → active → degraded states
- **Resilience** - Retry policies, circuit breakers, dead letter queue
- **Multiple Channels** - Telegram, WhatsApp, Web, WebSocket, FTP, and more
- **CLI & Web UI** - Full management interface

## Installation

```powershell
# Clone and install
git clone https://github.com/yourrepo/unigate.git
cd unigate

# Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install in development mode
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -v
```

## Quick Start

### 1. Create Configuration

```yaml
# unigate.yaml
unigate:
  mount_prefix: /unigate

instances:
  web_ui:
    type: webui
    port: 8080

  sales_bot:
    type: telegram
    token: !env:TELEGRAM_BOT_TOKEN
    mode: polling

routing:
  default_action: keep
  rules:
    - name: sales-routing
      priority: 100
      match:
        text_contains: "sales"
      actions:
        forward_to: [sales_bot]
```

### 2. Start Server

```powershell
# Start all configured instances with unified routing
unigate serve --config unigate.yaml --port 8080

# Or use defaults (looks for unigate.yaml in current directory)
unigate serve
```

### 3. Access Routes

All instances share a single port with unified routing:

| Route | Description |
|-------|-------------|
| `GET /unigate/status` | Status dashboard with instance info |
| `GET /unigate/health` | Health check for load balancers |
| `GET /unigate/instances` | List all instances with states |
| `GET /unigate/web/{name}` | Web UI for webui channels |
| `POST /unigate/webhook/{name}` | Webhook for other channels |

Open `http://localhost:8080/unigate/web/web_ui/` to access the Web UI.

## Plugin System

### Available Plugins

| Type | Plugin | Description |
|------|--------|-------------|
| channel | web | Generic HTTP webhook |
| channel | webui | Built-in web UI for testing |
| channel | telegram | Telegram Bot API |
| channel | whatsapp | WhatsApp Business API |
| match | text_contains | Match message content |
| match | sender | Match by sender ID |
| match | from | Match by source instance |
| match | has_media | Match media presence |
| match | day_of_week | Match day of week |
| match | hour_of_day | Match hour of day |
| transform | truncate | Truncate message text |
| transform | add_metadata | Add metadata fields |
| transform | extract_subject | Extract subject line |
| transport | http | HTTP/HTTPS delivery |
| transport | websocket | WebSocket delivery |
| transport | ftp | FTP file transfer |
| transport | file | Local file output |

### List Available Plugins

```powershell
unigate plugins list
```

Output:
```
[+] channel    channel.telegram
[+] channel    channel.web
[+] channel    channel.webui
[+] channel    channel.whatsapp
[+] match      match.day_of_week
[+] match      match.from
[+] match      match.has_media
[+] match      match.sender
[+] match      match.text_contains
[+] transform  transform.add_metadata
[+] transform  transform.truncate
[+] transport  transport.file
[+] transport  transport.ftp
[+] transport  transport.http
[+] transport  transport.websocket
```

### Generate Config Template

```powershell
unigate plugins gen-config > plugins.yaml
```

## Routing Rules

Rules are defined in YAML. Lower priority number = higher priority (checked first).

### Match Conditions

```yaml
routing:
  rules:
    # By source instance
    - name: from-web
      priority: 100
      match:
        from_instance: web_ui
      actions:
        forward_to: [telegram_bot]
    
    # By text content
    - name: sales-keyword
      priority: 100
      match:
        text_contains: "sales"
      actions:
        forward_to: [sales_team]
    
    # By sender pattern (glob)
    - name: vip-users
      priority: 50
      match:
        sender_pattern: "vip_*"
      actions:
        forward_to: [vip_channel]
    
    # By group ID
    - name: dev-group
      priority: 100
      match:
        group_id: "dev-*"
      actions:
        forward_to: [dev_team]
    
    # Multiple conditions (AND logic)
    - name: vip-dev
      priority: 10
      match:
        sender_pattern: "vip_*"
        group_id: "dev-*"
      actions:
        forward_to: [vip_dev_channel]
    
    # Time-based
    - name: business-hours
      priority: 100
      match:
        hour_of_day: [9, 10, 11, 12, 13, 14, 15, 16, 17]
      actions:
        forward_to: [support_live]
```

### Actions

```yaml
routing:
  rules:
    - name: example
      priority: 100
      match:
        text_contains: "help"
      actions:
        forward_to: [support_bot]      # Forward to destination
        keep_in_default: true           # Also keep in source
        add_tags: [support, urgent]     # Add tags
```

## CLI Commands

```powershell
# Serve - Unified server with all configured instances
unigate serve                           # Start with unigate.yaml
unigate serve --config my.yaml         # Custom config
unigate serve --port 9000              # Custom port
unigate serve --mount-prefix /api      # Custom mount prefix

# Plugin management
unigate plugins list                    # List all plugins
unigate plugins status                  # Plugin summary
unigate plugins enable <name>           # Enable a plugin
unigate plugins disable <name>          # Disable a plugin
unigate plugins gen-config              # Generate config template

# Instance management
unigate instances list                  # List instances
unigate instances status                # Instance details

# Message operations
unigate inbox list                      # List inbox messages
unigate inbox show <id>                 # Show message
unigate inbox replay <id>              # Replay message

unigate outbox list                     # List outbox
unigate outbox retry                   # Retry failed
unigate outbox fail <id>               # Mark as failed

unigate dead-letters                    # View dead letters
unigate logs                           # View events
unigate health                         # Health check

# Daemon operations
unigate start                          # Start daemon
unigate stop                           # Stop daemon
unigate status                         # Status
```

## Development

### Run Tests

```powershell
python -m pytest tests/ -v
```

### Project Structure

```
unigate/
├── src/unigate/
│   ├── plugins/           # Plugin directory (flat)
│   │   ├── base.py        # Plugin registry & protocols
│   │   ├── channel_*.py  # Channel plugins
│   │   ├── match_*.py    # Matcher plugins
│   │   ├── transform_*.py # Transform plugins
│   │   └── transport_*.py # Transport plugins
│   ├── routing.py         # Routing engine
│   ├── lifecycle.py       # Instance states
│   ├── instance_manager.py # Lifecycle orchestration
│   ├── kernel.py         # Exchange kernel
│   ├── stores.py         # Storage backends
│   └── cli.py            # CLI commands
├── tests/
│   ├── test_*.py         # Unit tests
│   └── test_routing_comprehensive.py  # Routing tests
└── docs/
    ├── plugin-development.md
    └── architecture.md
```

## Documentation

- [Plugin Development Guide](docs/plugin-development.md) - Create new plugins
- [Architecture Overview](docs/architecture.md) - System design
- [Routing Configuration](docs/routing.md) - Routing rules reference
- [Plugin Architecture](docs/plugin-architecture.md) - Plugin system details

## Implementation Status

### Core Features (from PRD)
| Feature | Status |
|---------|--------|
| Message type | ✅ Implemented |
| BaseChannel contract | ✅ Implemented |
| Channel lifecycle | ✅ Implemented |
| Exchange kernel | ✅ Implemented |
| Storage (SQLite/Memory) | ✅ Implemented |
| Deduplication | ✅ Implemented |
| Retry policy | ✅ Implemented |
| Circuit breaker | ✅ Implemented |
| Health checks | ✅ Implemented |
| Extension chain | ⚠️ Basic |
| Session store | ✅ Implemented |
| SecureStore | ✅ Implemented |

### Channels
| Channel | Status |
|---------|--------|
| Telegram | ✅ Implemented |
| WhatsApp | ✅ Implemented |
| Web/Webhook | ✅ Implemented |
| WebUI | ✅ Implemented |
| Internal | ✅ Implemented |
| Slack | ❌ Not implemented |
| Discord | ❌ Not implemented |
| Email | ❌ Not implemented |
| SMS | ❌ Not implemented |

### Routing (Beyond PRD)
| Feature | Status |
|---------|--------|
| Rule-based routing | ✅ Implemented |
| YAML configuration | ✅ Implemented |
| Multiple matchers | ✅ Implemented |
| Transform extensions | ✅ Implemented |
| Priority ordering | ✅ Implemented |

### CLI Commands
| Command | Status |
|---------|--------|
| Plugin management | ✅ Implemented |
| Instance listing | ✅ Implemented |
| Inbox operations | ✅ Implemented |
| Outbox operations | ✅ Implemented |
| Dead letter queue | ✅ Implemented |
| Health checks | ✅ Implemented |

## License

MIT
