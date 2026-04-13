# Phase 1 Plan

## Objective

Phase 1 proves the kernel without any dependency on a real messaging platform.
If this phase is weak, every later adapter will inherit that weakness.

The target is not "some scaffolding." The target is a locally testable kernel
that can:

- receive inbound payloads
- normalize them
- persist them durably
- call a handler
- write and deliver outbound responses
- recover correctly after restart

Status today:

- contracts are implemented
- an in-memory minimum runtime is implemented
- fake/internal channels support local end-to-end execution
- api/web/websocket-style in-process channels support local end-to-end execution
- a mountable ASGI surface is implemented for HTTP and websocket access
- SQLite-backed sessions, inbox, outbox, and deduplication are implemented
- richer replay/recovery behavior is still pending

## Public Deliverables

The initial implementation should introduce these module areas inside
`src/unigate/`:

- `envelope.py`: normalized message contracts
- `channel.py`: channel capabilities and base adapter protocol
- `session.py`: session records and lookup/update logic
- `dedup.py`: duplicate detection contract and implementations
- `events.py`: internal operational events
- `inbox.py`: durable inbound pipeline
- `outbox.py`: durable outbound pipeline
- `instance.py`: instance state registry and lifecycle transitions
- `extension.py`: inbound and outbound extension hooks
- `interactive.py`: interaction correlation tracking
- `config.py`: config loading and environment interpolation
- `gate.py`: public entry point for embedding

The Phase 1 non-core support surface should include:

- in-memory backend implementations
- SQLite backend implementations
- `internal` channel
- `fake` test channel
- test kit for deterministic end-to-end coverage

## Implementation Order

### Step 1: Contracts

Define the stable data contracts first:

- `UniversalMessage`
- `OutboundMessage`
- sender and media models
- interaction payloads
- channel setup and health enums
- sender canonical identity reference populated outside core

Exit requirement:

- contracts are typed, importable, and documented
- per-instance outbound targeting is explicit in the contract shape

### Step 2: Durable Storage Interfaces

Implement the abstract interfaces and in-memory versions for:

- inbox
- outbox
- session store
- deduplication store
- secure key-value store placeholder

Exit requirement:

- the kernel can run entirely in memory for tests

### Step 3: SQLite Backends

Add SQLite-backed persistence for the same interfaces.

Exit requirement:

- restart simulation can recover inbox and outbox state

### Step 4: Instance Registry And Event Bus

Implement:

- instance registration
- state transitions
- event emission
- lifecycle hooks for start, stop, and reconnect intents

Exit requirement:

- multiple instances can coexist without shared failure state

### Step 5: Inbox Processing Path

Implement the inbound pipeline:

1. deduplicate
2. persist raw receipt
3. acknowledge source
4. normalize
5. correlate interactions
6. run extensions
7. call the handler
8. mark processed

Exit requirement:

- fake inbound events produce handler invocations exactly once

### Step 6: Outbox Processing Path

Implement:

- fan-out record creation
- per-instance send concurrency limits
- send attempts
- retries
- pending-state handling for inactive instances

Exit requirement:

- handler responses are delivered through the fake channel

### Step 7: Session And Reply Semantics

Implement:

- session creation and lookup
- mapping from channel session key to kernel session id
- reply-to-origin behavior for `to=[]`
- history summaries

Exit requirement:

- replies go back to the correct conversation after restart

### Step 8: Interaction Correlation

Implement:

- pending interaction tracking
- response matching
- timeout cleanup
- periodic sweeper

Exit requirement:

- interactive replies are matched and expired state is removed

### Step 9: Test Kit And End-To-End Coverage

Build a deterministic test harness around the fake channel.

Minimum end-to-end tests:

- inbound message receives outbound reply
- duplicate inbound message is ignored safely
- crash after inbox write replays correctly
- crash after outbox write retries correctly
- inactive instance leaves outbound work pending
- backpressure limits are enforced
- interaction response correlation works

## Non-Goals For Phase 1

Do not pull these into the first implementation slice:

- Telegram or any real external platform SDK
- OAuth or QR setup flows
- webhook routing
- MCP server integration
- rich channel-specific rendering
- content policy features such as allowlists or translation

## Commit Strategy

Phase 1 should be committed in narrow slices rather than one large drop.

Recommended sequence:

1. repo bootstrap and public docs
2. contracts and package layout
3. in-memory backends
4. SQLite backends
5. instance registry and events
6. inbox pipeline
7. outbox pipeline
8. sessions and interaction tracking
9. fake channel and test kit
10. end-to-end Phase 1 tests

This keeps `main` reviewable and makes open-source contribution easier from the
start.
