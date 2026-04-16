# Contributing

## Rewrite Context

This repository is under a clean rewrite to the 1.5 architecture. Do not carry
forward assumptions from the discarded prototype unless they clearly match the
new public contracts.

## Core Rules

- one universal `Message`
- one channel adapter contract
- transport-only kernel
- one outbound record per destination instance
- capability degradation belongs to adapters
- embedded and standalone share the same runtime

## Development Order

1. contracts
2. storage backends
3. exchange kernel
4. instance manager
5. extensions
6. router / CLI
7. simple adapters
8. real external adapters

## Standards

- Python 3.11+
- typed public interfaces
- tests for each architecture slice
- no business logic in kernel core
