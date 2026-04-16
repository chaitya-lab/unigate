# Roadmap

## Implemented in 1.5 baseline

- universal `Message` + adapter contract
- inbox/outbox/session/dedup/secure storage roles
- in-memory and SQLite durable stores
- exchange ingest/enqueue/flush pipeline with retry bookkeeping
- per-destination fan-out and session-origin fallback routing
- instance lifecycle manager with setup and health transitions
- extension interfaces (inbound/outbound/event)
- mountable ASGI runtime surface
- minimal CLI operations
- internal and fake webhook adapters for development

## Next milestones

### External adapters

- Telegram
- WhatsApp
- Discord
- Slack

### Operability hardening

- richer metrics and tracing events
- dead-letter support for terminal failures
- richer retry policies per instance/channel

### Developer experience

- advanced CLI filtering and diagnostics
- adapter scaffolding templates
- contract test kit for third-party adapters
