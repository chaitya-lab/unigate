# Architecture

`unigate` 1.5 is built around three transport components and strict responsibility boundaries.

## Components

### Exchange kernel

The `Exchange` owns transport guarantees:

- inbound pipeline: receive -> dedup -> durable inbox write -> handler dispatch
- outbound pipeline: destination resolution -> per-destination outbox records -> send -> retry bookkeeping
- event emission and extension invocation
- backpressure via bounded semaphore

### Instance manager

`InstanceManager` tracks state transitions for each registered instance:

- `unconfigured`
- `setup_required`
- `setting_up`
- `active`
- `degraded`
- `reconnecting`

### Channel adapters

Adapters implement `BaseChannel` and contain channel-specific behavior:

- raw payload -> `Message` (`to_message`)
- `Message` -> transport send (`from_message`)
- capability declaration and downgrade behavior
- setup/auth/health hooks

## Storage model

The exchange depends on five store roles:

- inbox store (durable inbound record)
- outbox store (durable pending/sent/retry records)
- session store (origin resolution for `to: []`)
- dedup store (idempotent inbound processing)
- secure store (per-instance credentials)

Built-in implementations:

- `InMemoryStores` for local runtime/testing
- `SQLiteStores` for restart-safe persistence

## Extensions

Hook chains support transport-safe customization:

- inbound extensions
- outbound extensions
- event extensions

Each hook can mutate or drop the item while preserving persistence order guarantees.

## Runtime interfaces

- Mountable ASGI app: `UnigateASGIApp`
- Routes:
  - `/{mount_prefix}/webhook/{instance_name}`
  - `/{mount_prefix}/status`
  - `/{mount_prefix}/health`
- CLI operations: `serve`, `status`, `instances`, `inbox`, `outbox`
