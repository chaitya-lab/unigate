# Roadmap

## Implemented (v0.2.0)

### Core
- [x] Universal `Message` type (all fields per PRD)
- [x] BaseChannel adapter contract
- [x] Exchange: ingest, enqueue, flush pipeline
- [x] Inbox/Outbox/Session/Dedup stores
- [x] InMemory and SQLite backends
- [x] Interactive correlation (pending interactions)
- [x] Circuit breaker resilience
- [x] Retry with exponential backoff
- [x] Dead letter handling

### Channels
- [x] `internal` - In-process messaging
- [x] `web` - Generic HTTP webhook (HMAC, Bearer, API Key auth)
- [x] `webui` - Web UI for testing (send/receive via browser)
- [x] `telegram` - Telegram Bot API (polling mode)
- [ ] `telegram` webhook mode
- [ ] WhatsApp
- [ ] Discord
- [ ] Slack
- [ ] Email (SMTP/IMAP)
- [ ] SMS (Twilio)

### Runtime
- [x] ASGI app surface
- [x] CLI daemon mode (start/stop/status)
- [x] Complete CLI (inbox/outbox/send/health/logs)
- [x] Webhook router with instance dispatch
- [x] Health check polling (per-instance and aggregate)
- [x] Plugin discovery (entry points + plugin_dirs)
- [x] Extension interfaces (inbound/outbound/event)
- [x] TestKit and FakeChannel

### Storage
- [x] InMemoryStores
- [x] SQLiteStores with retention_days
- [x] FileStores (file-per-message, multi-instance ready)
- [ ] RedisStores
- [ ] Fernet encryption for SecureStore

### Resilience
- [x] Circuit breaker per instance
- [x] Exponential backoff retry
- [x] Dead letter queue
- [x] Fallback instances
- [x] Graceful shutdown (flush outbox on SIGTERM)
- [x] Pending outbox recovery on restart
- [x] Instance state change events (activated/deactivated)
- [x] Auto-flush outbox when instance becomes ACTIVE

### Routing System (v0.2.1)
- [x] Config-based routing rules
- [x] Priority-based rule evaluation
- [x] Pattern matching (glob, regex)
- [x] Multiple destinations per rule
- [x] Default instance for unmatched messages
- [x] Multi-file routing config support
- [x] **Matcher plugins** (channel, sender, text, subject, media, time)
- [x] **Transform plugins** (truncate, extract_subject, add_metadata)
- [x] **Transport plugins** (HTTP, FTP, WebSocket)

### Plugin Architecture
- [x] Unified plugin system with type-based discovery
- [x] `plugin_dirs` config for user plugins
- [x] Built-in plugins: channels, transforms, transports, matchers
- [x] Routing rules as user config (outside plugins)
- [x] See [docs/plugin-architecture.md](plugin-architecture.md) for full design

## Testing Checklist

- [x] Basic message flow (send/receive)
- [x] Echo response
- [x] Dedup (same message ID)
- [x] Session routing
- [x] Fan-out (broadcast to multiple instances)
- [x] Circuit breaker
- [x] **Interactive - Confirm buttons**
- [x] **Interactive - Select options**
- [x] **Group mentions (ignore unless @mentioned)**
- [x] **Thread support**
- [x] **Media send**
- [x] **Typing indicator**
- [x] **Message edit**
- [x] **Message delete**
- [x] **Message reactions**
- [x] **Routing rules**
- [x] **Matcher plugins**
- [x] **Transform plugins**

## Next Steps

### Transport Instance Type
- [ ] Transport instance type for sending via FTP/WebSocket/etc.
- [ ] Built-in transports: HTTP, FTP, WebSocket, Email, SMS

### Handler Instance
- [ ] Handler as special "handler" instance type
- [ ] Remove fixed handler from gate.py
- [ ] Handler destination in routing rules

### More Built-in Matchers
- [ ] Metadata matcher (match by metadata fields)
- [ ] Combined condition matcher (AND/OR logic)

### More Built-in Transforms
- [ ] HTML to text conversion
- [ ] Language detection
- [ ] Profanity filter

## Deferred (Phase 4+)

### External Adapters
- WhatsApp Cloud API
- Discord (webhook + bot)
- Slack (OAuth)
- Email (SMTP/IMAP)
- SMS (Twilio)
- WebSocket server channel
- `telegram` webhook mode

### Features
- Fernet encryption for credentials
- Redis multi-instance backend
- MCP interface
- Adapter scaffolding templates
- Contract test kit

### Production Hardening
- Metrics and tracing
- Configuration hot-reload
- Setup state machine (OAuth/QR auth lifecycle)
