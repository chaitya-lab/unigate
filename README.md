# unigate

`unigate` is an MIT-licensed universal messaging gateway for agentic systems.
It manages authenticated channel connections, normalizes inbound traffic into a
single envelope, and provides durable outbound delivery across process restarts.

The kernel is transport-focused by design. It does not implement agent logic,
business workflows, routing policy, or LLM behavior. Those belong in the parent
application, channel adapters, or extensions.

## Status

This repository now includes a working minimum runtime for local, in-memory
message flow. It is still early-stage, but the kernel can already:

- register channel instances
- ingest inbound text events
- create transport-local sessions
- deduplicate inbound messages
- record inbox and outbox state in memory
- invoke a handler
- deliver replies through a fake/internal channel
- emit operational events for the flow

Current priorities:

- Extend the minimum runtime beyond in-memory state.
- Add real backends and richer lifecycle/state handling.
- Keep `internal` and `fake` channels as the first proof path without external
  platform SDKs.
- Add real channels only after the kernel contracts are proven.

## Design Principles

- Thin kernel, fat extensions.
- Zero special cases across embedded, standalone, and MCP-enabled deployments.
- Durable delivery before convenience.
- Multi-instance isolation by default.
- Per-instance outbound delivery as the core primitive.
- Open adapter model: new channels should not require core modification.

## Initial Scope

Phase 1 focuses on the universal kernel:

- normalized inbound and outbound message models
- one outbound intent per destination instance
- durable inbox and outbox
- session tracking
- interaction correlation
- extension hooks
- instance lifecycle management
- fake and internal test channels
- SQLite and in-memory backends

Real platform adapters such as Telegram, WhatsApp, Slack, and SMS follow in
later phases.

## Working Minimum

The current minimum working product is in-memory only. It is useful for:

- local development
- API shape validation
- adapter contract validation
- end-to-end tests without external dependencies

Implemented runtime pieces:

- `Unigate` runtime orchestration
- in-memory sessions, inbox, outbox, deduplication, and event bus
- `InternalChannel`
- `ApiChannel`
- `WebChannel`
- `WebSocketServerChannel`
- `FakeChannel`
- mountable ASGI integration for HTTP and websocket access
- end-to-end tests using `unittest`

## Documentation

- [Architecture](docs/architecture.md)
- [Roadmap](docs/roadmap.md)
- [Phase 1 Plan](docs/phase-1.md)
- [Contributing](CONTRIBUTING.md)

## Planned Repository Shape

```text
src/unigate/      core package
docs/             public architecture and contributor docs
tests/            unit and integration coverage
examples/         reference embeddings and local demos
```

As the implementation grows, built-in channels and optional modules will remain
separate from the kernel's stable transport contracts.

## Development

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]
python -m unittest discover -s tests
```

## Quickstart

```python
from unigate import Unigate
from unigate.channels import ApiChannel

gate = Unigate()
channel = ApiChannel()
gate.register_instance("public_api", channel)

@gate.on_message
def handle(message):
    return gate.reply(message, text=f"echo: {message.text}")
```

Then drive an inbound event through the API channel:

```python
await channel.receive_request(
    request_id="req-1",
    client_id="user-1",
    sender_name="User One",
    text="hello",
    conversation_id="chat-1",
)
```

The reply is captured in `channel.sent_messages`.

## ASGI Integration

You can mount `unigate` inside another ASGI app or run it behind a simple ASGI
server.

```python
from unigate import Unigate, create_asgi_app

gate = Unigate()
app = create_asgi_app(gate, prefix="/unigate")
```

Available endpoints in the current minimum version:

- `POST /unigate/channels/api/{instance}/messages`
- `POST /unigate/channels/web/{instance}/messages`
- `WS /unigate/channels/ws/{instance}`

This keeps embedded and standalone usage aligned around the same runtime.

## Relationship To The Larger System

`unigate` is one component inside a larger agentic OS effort, but this
repository is intentionally standalone. It should be understandable,
installable, testable, and reusable outside the rest of the system.
