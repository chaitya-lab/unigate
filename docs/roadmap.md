# Roadmap

## Delivery Strategy

The implementation should move in layers. Kernel contracts and local testability
come first. Real channels come only after the core durability model is proven.

## Phase 1: Kernel Core

Target outcome: a fully testable messaging kernel with no external platform
dependencies.

Deliverables:

- message envelope and outbound contract
- base channel and extension contracts
- instance registry and lifecycle state machine
- in-memory and SQLite backends
- durable inbox and outbox
- session tracking
- deduplication
- interaction correlation with timeout cleanup
- internal event bus
- `internal` and `fake` channels
- test kit and fixtures

Exit criteria:

- fake channel can receive inbound traffic and deliver outbound responses
- inbox and outbox survive restart
- duplicate inbound events are not reprocessed
- session creation and reply routing work
- interaction responses correlate correctly
- global backpressure limits are enforced without dropping messages

## Phase 2: HTTP Edge And First Real Channels

Target outcome: the kernel can accept webhook traffic and support at least one
real chat platform.

Deliverables:

- webhook router with mountable ASGI integration
- configurable webhook prefix
- CLI channel
- Telegram adapter with polling and webhook modes
- outbox replay CLI support for operational recovery

Exit criteria:

- a real Telegram message reaches the handler and is replied to correctly
- webhook verification and routing are stable
- pending outbound work can be replayed after recovery

## Phase 3: Auth Lifecycle And Standalone Topology

Target outcome: stateful channel setup flows and standalone deployment work.

Deliverables:

- setup lifecycle orchestration
- secure store with encryption support
- WhatsApp QR-based channel
- Slack OAuth-based channel
- `websocket_server` channel for parent-process integration
- watchdogs for stale setup and route reconciliation

Exit criteria:

- setup-required flows work without restarting the process
- credentials can expire and recover through the lifecycle state machine
- standalone `unigate serve` can connect to a parent application over WebSocket

## Phase 4: Ecosystem And Packaging

Target outcome: the project is usable as a public open-source platform.

Deliverables:

- extension system completion
- first-party extensions
- optional MCP module
- complete CLI surface
- packaging and release automation
- contributor examples and adapter authoring guides

Exit criteria:

- external contributors can add a channel without modifying kernel internals
- MCP-compatible clients can use the gateway without custom glue code
- packaging and documentation support independent adoption

## Cross-Cutting Requirements

These apply to all phases:

- semantic versioning for the package
- explicit compatibility for adapter contracts
- docs updated alongside behavior changes
- no private-planning artifacts in the public repo
- each major phase ends with runnable tests, not just scaffolding
