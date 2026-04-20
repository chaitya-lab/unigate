# Configuration Reference

Complete reference for all configuration options in `unigate.yaml`.

---

## Config File Structure

```yaml
# Required: unigate settings
unigate:
  mount_prefix: /unigate

# Optional: Storage settings
storage:
  backend: memory
  path: ./unigate.db

# Required: Channel instances
instances:
  my_channel:
    type: channel_type
    enabled: true    # Optional: include/exclude without deleting
    # ... channel config

# Optional: Extensions
extensions:
  - name: extension_name
    enabled: true    # Optional: enable/disable

# Optional: Routing rules
routing:
  default_action: keep
  rules:
    - name: rule-name
      enabled: true    # Optional: enable/disable
```

---

## Multi-File Config Support

UniGate supports splitting config into multiple files:

### Using File References

```yaml
# unigate.yaml - main config
unigate:
  mount_prefix: /unigate

storage:
  backend: memory

instances_file: instances.yaml
routing_file: routing.yaml
extensions_file: extensions.yaml
```

```yaml
# instances.yaml
web1:
  type: web

web2:
  type: web

telegram:
  type: telegram
  token: !env:TELEGRAM_BOT_TOKEN
```

```yaml
# routing.yaml
default_action: keep
rules:
  - name: web1-to-web2
    match:
      from_instance: web1
    actions:
      forward_to: [web2]
```

### Using !include Directive

```yaml
# unigate.yaml - inline includes
unigate:
  mount_prefix: /unigate

instances: !include instances.yaml
routing: !include routing.yaml
```

---

## Enable/Disable

There are **two** levels of enable/disable:

### 1. Config-Level (`enabled:` in YAML)

Controls whether instances/rules are loaded at startup.

```yaml
instances:
  web1:
    type: web
    enabled: true    # loaded

  web2:
    enabled: false   # not loaded

routing:
  rules:
    - name: active-rule
      enabled: true

    - name: paused-rule
      enabled: false    # not loaded
```

| Key | Effect |
|-----|--------|
| `enabled: true` | Include (default) |
| `enabled: false` | Exclude |
| No `enabled` key | Include (default) |

### 2. Runtime (CLI Commands)

Controls whether running instances/processes are active:

```bash
unigate instances enable telegram    # Start processing
unigate instances disable telegram  # Stop processing

unigate plugins enable telegram      # Activate plugin
unigate plugins disable telegram    # Deactivate plugin
```

- CLI commands affect *running* instances (require server to be running)
- Config YAML affects *what loads* at startup

---

## Instance Lifecycle States

Instances have lifecycle states that indicate their current status:

| State | Description |
|-------|-------------|
| `active` | Instance is running and healthy |
| `degraded` | Instance is running but has issues (e.g., auth problems) |
| `reconnecting` | Attempting to recover from errors |
| `setup_required` | Needs user interaction (e.g., auth token) |
| `disabled` | Manually disabled |

### Health Checks

UniGate runs automatic health checks every 60 seconds when running as a daemon. Channels report:

- **healthy** - Channel can send/receive
- **unhealthy** - Auth failed or channel down
- **unknown** - Not configured

```bash
# Check instance health
unigate instances health telegram
```

If an instance becomes unhealthy, UniGate will:
1. Update state to `degraded`
2. Continue routing messages (may fail)
3. Emit `health.degraded` events

### Manual Health Check

Force a fresh health check:

```bash
unigate instances health telegram --force
```

---

## `unigate` Section

Global settings for the unigate server.

```yaml
unigate:
  mount_prefix: /unigate    # URL prefix for all routes
  plugin_dirs:              # Optional: Additional plugin directories
    - ./my_plugins
    - /opt/unigate/plugins
  loaded_plugins: "*"       # "*" or list of patterns (e.g., ["channel.*", "match.text_*"])
  disabled_plugins: []      # List of plugins to skip (supports wildcards)
  max_concurrent_processing: 50  # Max simultaneous message processing
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `mount_prefix` | string | `/unigate` | URL prefix for HTTP routes |
| `plugin_dirs` | list | `[]` | Directories to scan for plugins |
| `loaded_plugins` | string/list | `"*"` | Plugin patterns to load (supports wildcards, e.g., `"channel.*"`, `"match.text_*"`) |
| `disabled_plugins` | list | `[]` | Plugins to exclude (supports wildcards) |
| `max_concurrent_processing` | int | `50` | Max concurrent message processing |

### Plugin Filtering

The `loaded_plugins` and `disabled_plugins` options support wildcard patterns using `fnmatch`:

```yaml
unigate:
  # Load only channels and specific matchers
  loaded_plugins:
    - "channel.*"        # All channels
    - "match.text_*"     # All text matchers (text_contains, text_starts, etc.)
    - "transform.*"      # All transforms
    - "transport.http"   # Specific transport
  
  # Exclude specific plugins
  disabled_plugins:
    - "channel.telegram" # Don't load Telegram
    - "match.day_of_week" # Don't load day matcher
```

Common patterns:
- `"*"` - Load all plugins (default)
- `"channel.*"` - All channels
- `"match.*"` - All matchers
- `"transform.*"` - All transforms
- `"transport.*"` - All transports
- `"match.text_*"` - All text-based matchers

---

## `storage` Section

Storage backend configuration.

```yaml
storage:
  backend: memory  # memory | sqlite | file
  path: ./unigate.db
```

### Backends

#### Memory (Development)

```yaml
storage:
  backend: memory
```

- Fast, no persistence
- Data lost on restart
- Good for testing

#### SQLite (Production)

```yaml
storage:
  backend: sqlite
  path: ./unigate.db
  retention_days: 7           # Days to keep messages
  dedup_retention_days: 1     # Days to keep dedup keys
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `path` | string | `./unigate.db` | SQLite file path |
| `retention_days` | int | `7` | Days to keep messages |
| `dedup_retention_days` | int | `1` | Days to keep dedup keys |

#### File (Debug)

```yaml
storage:
  backend: file
  path: ./unigate_messages
  retention_days: 7
  cleanup_interval_seconds: 3600
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `path` | string | `./unigate_messages` | Directory for message files |
| `retention_days` | int | `7` | Days to keep files |
| `cleanup_interval_seconds` | int | `3600` | Cleanup interval |

---

## `instances` Section

Define channel instances. Each instance connects to one channel.

```yaml
instances:
  instance_name:
    type: channel_type
    
    # Channel-specific options
    token: !env:VARIABLE_NAME
    mode: polling
    
    # Optional: Resilience settings
    retry:
      max_attempts: 5
      base_delay_seconds: 2
      max_delay_seconds: 30
    
    circuit_breaker:
      failure_threshold: 5
      recovery_timeout: 60
```

### Channel Types

#### webui - Built-in Web Interface

```yaml
instances:
  web:
    type: webui
    config:
      title: "My Chat"     # Custom title for the UI
      theme: dark         # light or dark theme
```

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| `title` | string | No | Custom title for the web UI |
| `theme` | string | No | `light` or `dark` (default: `dark`) |
| `token` | string | No | Single API token for authentication |
| `tokens` | list | No | Multiple tokens: `["user1:token1", "user2:token2"]` |

**With authentication:**

```yaml
instances:
  web:
    type: webui
    config:
      title: "My Chat"
      theme: dark
      # Single token (simple auth)
      token: "my-secret-token"
      
      # OR multiple tokens with usernames
      tokens:
        - "admin:admin-token"
        - "user1:user1-token"
        - "user2:user2-token"
```

Token format for requests:
- Header: `Authorization: Bearer <token>`
- Or query param: `?token=<token>`

The tokens are checked against the configured `token` or the token part after `:` in `tokens` list.

#### web - Generic Webhook

```yaml
instances:
  webhook:
    type: web
    auth_method: none      # none | hmac | bearer | api_key
    secret: "secret"       # For HMAC signature verification
    bearer_token: "token" # For bearer auth
    api_key: "key"        # For API key auth
    api_key_header: X-API-Key  # Header name for API key
```

#### telegram - Telegram Bot

```yaml
instances:
  my_bot:
    type: telegram
    token: !env:TELEGRAM_BOT_TOKEN
    mode: polling  # polling | webhook
    webhook_url: https://example.com/unigate/webhook/my_bot
```

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| `token` | string | Yes | Bot token from @BotFather |
| `mode` | string | No | `polling` (default) or `webhook` |
| `webhook_url` | string | No | URL for webhook mode |

#### whatsapp - WhatsApp Business

```yaml
instances:
  whatsapp:
    type: whatsapp
    api_key: !env:WHATSAPP_API_KEY
    phone_number_id: "123456789"
    business_account_id: "BUSINESS_ID"
```

#### internal - Internal Handler

```yaml
instances:
  handler:
    type: internal
```

Used when your code directly calls the exchange.

### Instance Resilience Settings

#### Retry Policy

```yaml
instances:
  my_channel:
    type: telegram
    token: !env:TOKEN
    retry:
      max_attempts: 5           # Max retry attempts
      base_delay_seconds: 2    # Initial delay
      max_delay_seconds: 30    # Max delay
      strategy: exponential     # exponential | linear | fixed
      jitter: true            # Add randomness to delays
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `max_attempts` | int | `5` | Max retry attempts |
| `base_delay_seconds` | int | `2` | Initial delay |
| `max_delay_seconds` | int | `30` | Max delay |
| `strategy` | string | `exponential` | Backoff strategy |
| `jitter` | bool | `true` | Add randomness |

#### Circuit Breaker

```yaml
instances:
  my_channel:
    type: telegram
    token: !env:TOKEN
    circuit_breaker:
      failure_threshold: 5      # Failures before opening
      recovery_timeout: 60     # Seconds before half-open
      half_open_max_requests: 1  # Requests in half-open state
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `failure_threshold` | int | `5` | Failures to open circuit |
| `recovery_timeout` | int | `60` | Seconds before retry |
| `half_open_max_requests` | int | `1` | Test requests in half-open |

#### Fallback Instances

```yaml
instances:
  primary_telegram:
    type: telegram
    token: !env:PRIMARY_TOKEN
    fallback:
      - secondary_telegram
      - sms_backup

  secondary_telegram:
    type: telegram
    token: !env:SECONDARY_TOKEN

  sms_backup:
    type: sms
    provider: twilio
```

When primary fails, messages route to fallbacks.

---

## `extensions` Section

Extensions transform messages in the pipeline.

```yaml
extensions:
  - name: identity
    priority: 10
    config:
      auto_detect: true
      names:
        user123: "John Doe"
      links:
        telegram_123: canonical_user_1

  - name: pii_redact
    priority: 20
    config:
      redact_phone: true
      redact_email: true
```

### Built-in Extensions

#### identity

Links users across platforms and provides friendly names.

```yaml
extensions:
  - name: identity
    config:
      auto_detect: true           # Auto-detect phone/email patterns
      names:                     # Map sender IDs to names
        "12345": "John Doe"
        "67890": "Jane Smith"
      links:                     # Link cross-platform IDs
        telegram_123: canonical_user
        whatsapp_456: canonical_user
```

#### pii_redact

Redacts personally identifiable information.

```yaml
extensions:
  - name: pii_redact
    config:
      redact_phone: true
      redact_email: true
      redact_credit_card: true
      redact_ssn: true
      replacement: "[REDACTED]"
```

---

## `routing` Section

Rule-based message routing.

```yaml
routing:
  default_action: keep  # keep | discard | forward
  default_instance: null
  rules:
    - name: rule-name
      priority: 100
      enabled: true
      match:
        # Match conditions
      actions:
        # Routing actions
```

### `default_action`

What to do with messages that don't match any rule.

| Value | Description |
|-------|-------------|
| `keep` | Store in unprocessed (default) |
| `discard` | Drop the message |
| `forward` | Forward to `default_forward_to` |

### `default_forward_to`

When `default_action: forward`, specify destination instances:

```yaml
routing:
  default_action: forward
  default_forward_to: [archive_channel]
```

### Routing Rules

Each rule has:

```yaml
routing:
  rules:
    - name: rule-name           # Unique name
      priority: 100             # Lower = higher priority
      enabled: true            # Can disable without deleting
      match:                   # Conditions (all must match)
        from_instance: web
      actions:                 # What to do
        forward_to: [telegram_bot]
```

#### Match Conditions

| Condition | Example | Description |
|-----------|---------|-------------|
| `from_instance` | `web` | Source channel name |
| `text_contains` | `"hello"` | Text contains substring |
| `text_pattern` | `"^/cmd.*"` | Regex pattern |
| `text_starts_with` | `"/"` | Text starts with |
| `sender` | `"user123"` | Exact sender ID |
| `sender_pattern` | `"vip_*"` | Glob pattern for sender |
| `sender_name_contains` | `"John"` | Sender name contains |
| `sender_domain` | `"@company.com"` | Email domain |
| `group_id` | `"support"` | Group ID |
| `has_media` | `true` | Has attachments |
| `has_attachment` | `true` | Has attachments |
| `has_image` | `true` | Has image |
| `has_video` | `true` | Has video |
| `media_type` | `image` | Specific media type |
| `day_of_week` | `["monday", "friday"]` | Days of week |
| `hour_of_day` | `[9, 10, 11, 12, 13, 14, 15, 16, 17]` | Hours (0-23) |

Multiple conditions are AND logic:

```yaml
match:
  from_instance: telegram_bot
  text_contains: "urgent"
  hour_of_day: [9, 10, 11, 12, 13, 14, 15, 16, 17]
```

#### Actions

```yaml
actions:
  forward_to: [telegram_bot]      # Forward to destinations
  keep_in_default: true            # Also keep in source
  add_tags: [urgent]              # Tag the message
```

| Action | Description |
|--------|-------------|
| `forward_to` | Forward to these instances |
| `keep_in_default` | Don't remove from source |
| `add_tags` | Add tags to message |

---

## Environment Variables

Use `!env:VARIABLE_NAME` syntax:

```yaml
instances:
  telegram:
    type: telegram
    token: !env:TELEGRAM_BOT_TOKEN
    api_key: !env:TELEGRAM_API_KEY
```

Environment variables can be set in:

```bash
# Linux/Mac
export TELEGRAM_BOT_TOKEN="123:abc"

# Windows
set TELEGRAM_BOT_TOKEN=123:abc

# Or in .env file (if using python-dotenv)
TELEGRAM_BOT_TOKEN=123:abc
```

---

## Complete Example

```yaml
# unigate.yaml
unigate:
  mount_prefix: /unigate
  plugin_dirs:
    - ./custom_plugins

storage:
  backend: sqlite
  path: ./unigate.db
  retention_days: 30

instances:
  # Web UI for testing
  web:
    type: webui

  # Primary Telegram bot
  primary_telegram:
    type: telegram
    token: !env:PRIMARY_TELEGRAM_TOKEN
    mode: polling
    fallback:
      - secondary_telegram
    retry:
      max_attempts: 5
      base_delay_seconds: 2
      max_delay_seconds: 60
    circuit_breaker:
      failure_threshold: 3
      recovery_timeout: 30

  # Secondary Telegram (fallback)
  secondary_telegram:
    type: telegram
    token: !env:SECONDARY_TELEGRAM_TOKEN
    mode: polling

  # Webhook receiver
  webhook:
    type: web
    auth_method: hmac
    secret: !env:WEBHOOK_SECRET

extensions:
  - name: identity
    priority: 10
    config:
      auto_detect: true
      names:
        "123456": "Support Bot"
      links:
        telegram_support: canonical_support

routing:
  default_action: keep
  rules:
    # Web messages to Telegram
    - name: web-to-telegram
      priority: 50
      match:
        from_instance: web
      actions:
        forward_to: [primary_telegram]

    # Webhook to Telegram
    - name: webhook-to-telegram
      priority: 50
      match:
        from_instance: webhook
      actions:
        forward_to: [primary_telegram]

    # Telegram back to Web
    - name: telegram-to-web
      priority: 50
      match:
        from_instance: primary_telegram
        text_contains: "support"
      actions:
        forward_to: [web]

    # VIP users always to primary
    - name: vip-routing
      priority: 10
      match:
        sender_pattern: "vip_*"
      actions:
        forward_to: [primary_telegram]
        add_tags: [vip]
```

---

## Validation

Check your config is valid:

```bash
unigate plugins validate --config unigate.yaml
```

---

## Next Steps

- [Routing](routing.md) - Detailed routing rules
- [Plugins](plugins.md) - Create custom channels
- [CLI](cli.md) - Manage running instance
