# Architecture

## What `unigate` is

`unigate` is a universal messaging kernel. It owns transport-level concerns:

- channel authentication lifecycle
- message normalization
- inbox durability
- outbound retry and fallback
- session tracking
- extension execution hooks
- operational events

It does not own agent logic, business rules, semantic routing, or content
policy. Those concerns live outside the kernel.

## Core Model

### Instance

An instance is one authenticated connection to one channel type, identified by
a logical name such as `sales_whatsapp` or `support_telegram`.

Multiple instances of the same channel type must remain fully isolated:

- separate auth state
- separate retry state
- separate circuit breakers
- separate durable outbox partitions

### Channel Type

A channel type is a transport implementation such as `telegram`, `whatsapp`,
`slack`, `sms`, `cli`, `internal`, or `websocket_server`.

The kernel should only depend on a stable channel contract. Adapters carry
platform-specific concerns.

### Envelope

All inbound traffic is normalized into a stable envelope. All outbound traffic
passes through a corresponding outbound contract. Kernel handlers and
extensions operate on those contracts rather than raw platform payloads.

The normalized model must preserve:

- instance identity
- session and thread mapping
- sender profile
- receiver context
- content payloads
- edit and delete signals
- raw payload provenance

### Session

A session is a durable conversation record keyed by a kernel-generated UUID and
mapped to the channel's natural conversation key.

Session state exists to support:

- reply targeting
- history lookup
- cross-restart continuity
- correlation of interactive workflows

## Lifecycle

Each instance follows a managed lifecycle:

`unconfigured -> setup_required -> setting_up -> active -> degraded -> reconnecting`

Important rules:

- adapters implement auth and health operations
- the kernel owns lifecycle transitions and emitted events
- expired credentials must return the instance to `setup_required`
- degraded or reconnecting behavior must not block unrelated instances

## Durability Model

### Inbox

Inbound flow is durable-first:

1. receive raw payload
2. deduplicate
3. write inbox record
4. acknowledge upstream platform
5. normalize and process
6. mark processed

This ordering lets the kernel survive crashes after receipt but before handler
execution.

### Outbox

Outbound flow is also durable-first:

1. handler produces outbound intent
2. write outbox records per destination
3. enforce instance-level send concurrency
4. attempt delivery
5. retry, fallback, or mark final state

This ensures messages are not lost when the process restarts or a channel is
temporarily unavailable.

## Extension Boundary

Extensions are hooks around transport flow, not a second kernel. They may:

- enrich metadata
- redact content
- resolve identity
- add observability

They should not mutate the kernel into a workflow engine.

## Deployment Modes

There are three public-facing ways to use the system, but only one kernel:

- embedded in a Python application
- standalone microservice
- optional MCP interface layered on the same APIs

The design target is zero special-case logic between these modes. They should
compose from the same primitives rather than diverge into separate products.

## Packaging Direction

The repository should evolve along these boundaries:

- core package for stable contracts and orchestration
- built-in channels with independent publishability
- optional extensions
- optional MCP module
- testing kit and fake adapters

The first implementation milestone is proving the kernel without any external
network dependency.
