# unigate

`unigate` is a transport-only messaging exchange for multi-channel systems.

It receives inbound payloads, deduplicates and stores them, routes handler output,
fans out per destination, retries failures, and exposes runtime operations through
ASGI routes and CLI commands.

## 1.5 architecture

- one universal `Message` contract for both directions
- adapter boundary (`BaseChannel`) for translation and capability degradation
- exchange pipelines for inbound and outbound message flow
- lifecycle-aware instances with setup and health transitions
- extension chain for inbound/outbound/event hooks
- durable store implementations (`InMemoryStores`, `SQLiteStores`)

## Runtime surfaces

- ASGI app: `UnigateASGIApp`
- routes: `/{mount_prefix}/webhook/{instance}`, `/{mount_prefix}/status`, `/{mount_prefix}/health`
- CLI: `unigate serve|status|instances|inbox|outbox`

## Development

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]
python -m unittest discover -s tests -v
```

## Documentation

- [Architecture](docs/architecture.md)
- [Roadmap](docs/roadmap.md)
- [Contributing](CONTRIBUTING.md)
