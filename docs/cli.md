# CLI Reference

Complete reference for all `unigate` CLI commands.

---

## Overview

The `unigate` CLI manages the messaging exchange:

- **Server** - Start/stop the HTTP server
- **Instances** - Manage channel instances
- **Messages** - View inbox, outbox, dead letters
- **Plugins** - List and manage plugins

---

## Global Options

These options work with all commands:

```bash
--config PATH, -c PATH     Config file (default: unigate.yaml)
--help, -h                  Show help
```

---

## Server Commands

### `start`

Start the unigate server.

```bash
unigate start [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--config, -c PATH` | Config file (default: unigate.yaml) |
| `--foreground, -f` | Run in foreground (Ctrl+C to stop) |
| `--port, -p N` | HTTP port (default: 8080) |
| `--host HOST` | Host to bind (default: 0.0.0.0) |
| `--mount-prefix PREFIX` | URL prefix (default: /unigate) |
| `--storage-path PATH` | Storage path (overrides config) |
| `--retention DAYS` | Retention days (overrides config) |

**Examples:**

```bash
# Start in background
unigate start

# Start in foreground
unigate start -f

# Custom port
unigate start --port 9000

# Custom config
unigate start --config production.yaml

# All options
unigate start -f --port 8080 --host 127.0.0.0
```

**Output:**

```
Unigate started (PID: 12345)
  Config: unigate.yaml
  Server: http://0.0.0.0:8080/unigate/
  Routes:
    GET  /unigate/status     - Status
    GET  /unigate/health    - Health
    GET  /unigate/instances - Instances
    GET  /unigate/web/web/  - Web UI
```

### `stop`

Stop the running server.

```bash
unigate stop
```

**Example:**

```bash
unigate stop
# Output: Daemon stopped
```

---

## Status Commands

### `status`

Show server status.

```bash
unigate status
```

**Example Output:**

```json
{
  "ok": true,
  "uptime_seconds": 3600,
  "instances": {
    "web": "active",
    "telegram": "active"
  },
  "stats": {
    "inbox_count": 150,
    "outbox_count": 5,
    "sessions_count": 42,
    "dead_letters_count": 2
  }
}
```

### `health`

Check health of all instances.

```bash
unigate health
```

**Example Output:**

```json
{
  "ok": true,
  "instances": {
    "web": "healthy",
    "telegram": "healthy",
    "whatsapp": "degraded"
  }
}
```

### `logs`

View recent events.

```bash
unigate logs [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--limit, -n N` | Number of events (default: 100) |
| `--type, -t PREFIX` | Filter by event type prefix |

**Examples:**

```bash
# Last 50 events
unigate logs --limit 50

# Only outbox events
unigate logs --type outbox

# Only errors
unigate logs --type error
```

---

## Instance Commands

### `instances list`

List all instances.

```bash
unigate instances list [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--state STATE` | Filter by state |

**Example:**

```bash
unigate instances list
```

**Output:**

```
INSTANCE          STATE      MESSAGES_IN  MESSAGES_OUT  ERRORS
web               active     1,234        1,200         0
telegram          active     5,678        5,600         0
whatsapp          degraded   200          180           3
```

### `instances status`

Show detailed instance status.

```bash
unigate instances status [INSTANCE_ID]
```

**Options:**

| Option | Description |
|--------|-------------|
| `INSTANCE_ID` | Specific instance (optional) |

**Examples:**

```bash
# All instances
unigate instances status

# Specific instance
unigate instances status telegram
```

**Output:**

```
Instance: telegram
  Type: telegram
  State: active
  Messages In: 5,678
  Messages Out: 5,600
  Errors: 0
  Circuit Breaker: closed
  Retry Policy: exponential (max 5 attempts)

Recent Errors:
  - None
```

### `instances enable`

Enable a disabled instance.

```bash
unigate instances enable INSTANCE_ID
```

**Example:**

```bash
unigate instances enable telegram
```

### `instances disable`

Disable an instance (stops processing messages).

```bash
unigate instances disable INSTANCE_ID
```

**Example:**

```bash
unigate instances disable whatsapp
```

### `instances health`

Check health status of one or more instances. Shows if channels can send/receive messages.

```bash
unigate instances health [INSTANCE_ID ...] [--force]
```

**Options:**
- `INSTANCE_ID` - Specific instance(s) to check (checks all if omitted)
- `--force, -f` - Force fresh health check

**Examples:**

```bash
# Check all instances
unigate instances health

# Check specific instance
unigate instances health telegram

# Check multiple instances
unigate instances health telegram whatsapp

# Force fresh check (bypass cache)
unigate instances health telegram --force
```

**Output shows:**
- `healthy` - Channel is working
- `unhealthy` - Auth failed or channel down
- `unknown` - Not configured or cannot determine

### `instances reload`

Reload an instance to pick up config changes (e.g., new token).

```bash
unigate instances reload INSTANCE_ID [--reset]
```

**Options:**
- `INSTANCE_ID` - Instance to reload
- `--reset, -r` - Reset credentials before reloading

**Examples:**

```bash
# Reload to pick up token change
unigate instances reload telegram

# Reset credentials then reload (if token was removed)
unigate instances reload telegram --reset
```

**Use cases:**
- Token changed in config (from BotFather, Twilio, etc.)
- Want to force re-read environment variables
- Instance is degraded due to auth issues

> Note: Other instances are unaffected during reload.

### `instances restart`

Restart a specific instance.

```bash
unigate instances restart INSTANCE_ID
```

**Example:**

```bash
unigate instances restart telegram
```

### `instances setup`

Force re-authentication for an instance.

```bash
unigate instances setup INSTANCE_ID
```

**Example:**

```bash
# For WhatsApp QR code re-auth
unigate instances setup whatsapp
```

---

## Message Commands

### `inbox list`

List received messages.

```bash
unigate inbox list [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--instance INSTANCE` | Filter by instance |
| `--status STATUS` | Filter by status (`received`, `processed`) |
| `--limit N` | Number of messages (default: 50) |

**Example:**

```bash
# All messages
unigate inbox list

# Only from Telegram
unigate inbox list --instance telegram

# Only processed
unigate inbox list --status processed

# Last 10
unigate inbox list --limit 10
```

**Output:**

```
ID                 INSTANCE    STATUS      TEXT                    TIME
msg_abc123         telegram    processed   "Hello bot"            2024-01-15 10:30
msg_def456         web        received    "Test message"           2024-01-15 10:29
msg_ghi789         telegram    processed   "/help"                2024-01-15 10:28
```

### `inbox show`

Show full message details.

```bash
unigate inbox show MESSAGE_ID
```

**Example:**

```bash
unigate inbox show msg_abc123
```

**Output:**

```json
{
  "id": "msg_abc123",
  "instance": "telegram",
  "from_instance": "telegram",
  "to": ["handler"],
  "session_id": "sess_xyz",
  "sender": {
    "id": "user123",
    "name": "John Doe",
    "platform_id": "123456"
  },
  "text": "Hello bot",
  "media": [],
  "status": "processed",
  "created_at": "2024-01-15T10:30:00Z"
}
```

### `inbox replay`

Replay a processed message (re-run routing).

```bash
unigate inbox replay MESSAGE_ID
```

**Example:**

```bash
unigate inbox replay msg_abc123
```

### `inbox skip`

Skip processing a message (mark as processed without routing).

```bash
unigate inbox skip MESSAGE_ID
```

**Example:**

```bash
unigate inbox skip msg_abc123
```

---

## Outbox Commands

### `outbox list`

List pending outbound messages.

```bash
unigate outbox list [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--instance INSTANCE` | Filter by destination |
| `--status STATUS` | Filter by status (`pending`, `delivered`, `failed`) |
| `--limit N` | Number of messages (default: 50) |

**Example:**

```bash
# All pending
unigate outbox list --status pending

# To specific instance
unigate outbox list --instance telegram
```

### `outbox show`

Show outbox message details.

```bash
unigate outbox show OUTBOX_ID
```

### `outbox retry`

Retry all failed messages.

```bash
unigate outbox retry
```

### `outbox fail`

Mark a message as permanently failed.

```bash
unigate outbox fail OUTBOX_ID
```

### `outbox skip`

Skip retry for a message (move to dead letters).

```bash
unigate outbox skip OUTBOX_ID
```

---

## Dead Letter Commands

Messages that exceeded retry limits go to dead letters.

### `dead-letters list`

List dead letters.

```bash
unigate dead-letters list [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--limit N` | Number of messages (default: 50) |

### `dead-letters show`

Show dead letter details.

```bash
unigate dead-letters show DL_ID
```

### `dead-letters requeue`

Requeue for retry.

```bash
unigate dead-letters requeue DL_ID
```

### `dead-letters purge`

Delete all dead letters (requires confirmation).

```bash
unigate dead-letters purge --confirm
```

---

## Plugin Commands

### `plugins list`

List all available plugins.

```bash
unigate plugins list [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--type TYPE` | Filter by type (`channel`, `match`, `transform`, `transport`) |
| `--enabled` | Only enabled plugins |
| `--disabled` | Only disabled plugins |

**Example:**

```bash
# All plugins
unigate plugins list

# Only channels
unigate plugins list --type channel

# Only enabled
unigate plugins list --enabled

# Only disabled
unigate plugins list --disabled
```

**Output:**

```
[+] channel    channel.telegram    Telegram Bot API
[+] channel    channel.web         Generic Webhook
[+] channel    channel.webui        Web UI
[-] channel    channel.whatsapp     WhatsApp Business
[+] match     match.text_contains  Text Contains
[+] match     match.sender         Sender Match
[+] transform transform.truncate    Truncate Text
[+] transport transport.http       HTTP Transport
```

Legend: `[+]` enabled, `[-]` disabled

### `plugins status`

Show plugin summary.

```bash
unigate plugins status [PLUGIN_NAME]
```

**Options:**

| Option | Description |
|--------|-------------|
| `PLUGIN_NAME` | Specific plugin |

**Example:**

```bash
# Summary
unigate plugins status

# Specific plugin
unigate plugins status telegram
```

### `plugins enable`

Enable a plugin.

```bash
unigate plugins enable PLUGIN_NAME
```

**Example:**

```bash
unigate plugins enable telegram
```

### `plugins disable`

Disable a plugin.

```bash
unigate plugins disable PLUGIN_NAME
```

### `plugins gen-config`

Generate configuration template for plugins.

```bash
unigate plugins gen-config [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--output, -o PATH` | Output file |

**Example:**

```bash
# Print to stdout
unigate plugins gen-config

# Save to file
unigate plugins gen-config --output my_plugins.yaml
```

### `plugins validate`

Validate configuration against plugins.

```bash
unigate plugins validate --config PATH
```

---

## Cleanup Commands

### `cleanup`

Run cleanup of old data.

```bash
unigate cleanup [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--dry-run` | Show what would be deleted |

**Example:**

```bash
# Preview what will be deleted
unigate cleanup --dry-run

# Actually delete
unigate cleanup
```

---

## Send Command

### `send`

Send a test message.

```bash
unigate send --to INSTANCE --text "message" [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--to INSTANCE` | Destination instance (required) |
| `--text TEXT` | Message text (required) |
| `--session SESSION_ID` | Session ID (optional) |

**Example:**

```bash
unigate send --to telegram --text "Hello from CLI!"
```

---

## Cheat Sheet

```bash
# Quick Start
unigate start -f                    # Start in foreground
unigate status                       # Check status
unigate health                       # Health check

# Instances
unigate instances list               # List all
unigate instances status telegram    # Telegram status
unigate instances enable telegram    # Enable
unigate instances disable telegram  # Disable

# Messages
unigate inbox list                  # View inbox
unigate inbox show msg_abc123       # Show message
unigate inbox replay msg_abc123     # Replay message
unigate outbox list                 # View outbox
unigate dead-letters list           # View failures

# Plugins
unigate plugins list                # List plugins
unigate plugins enable telegram    # Enable plugin
unigate plugins disable telegram   # Disable plugin

# Utilities
unigate logs --limit 50            # View logs
unigate cleanup                    # Cleanup old data
unigate send --to web --text "Hi"  # Send test message
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error |

---

## Configuration

The CLI reads from:

1. Command line options
2. Config file specified with `--config`
3. `unigate.yaml` in current directory

---

## Next Steps

- [Getting Started](getting-started.md) - Step-by-step tutorials
- [Configuration](configuration.md) - Config reference
- [Plugins](plugins.md) - Create custom plugins
