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

## Deferred (Phase 3+)

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
