# Architecture

## What `unigate` is

`unigate` is a messaging exchange.

It receives messages from instances, stores them durably, forwards them to the
correct destination, and retries failures. It does not interpret content.

## Three Components

### Exchange

The kernel owns:

- receive
- store
- forward
- retry
- events

### Instance

An instance is one named authenticated connection to one channel type.

### Channel Adapter

The adapter translates:

- platform payload -> `Message`
- `Message` -> platform payload

Capability degradation belongs here.

## One Universal `Message`

There is one message contract for both directions. Direction is context, not a
separate schema.

Important rule:

- core primitive is one outbound record per destination instance
- broadcasts are expanded into independent records

## Boundaries

Belongs in core:

- transport flow
- storage
- deduplication
- routing
- retry
- lifecycle

Does not belong in core:

- agent logic
- workflow logic
- business routing policy
- cross-channel identity resolution
- product-specific merged inbox views
