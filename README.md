# unigate

`unigate` is a messaging exchange.

It receives messages from channel instances, stores them durably, forwards them
to the correct destination, and retries failures without interpreting message
content.

This repository is now in the clean 1.5 rewrite. The old prototype
implementation is being replaced.

## Core Model

- the exchange moves messages
- instances are named authenticated connections
- channel adapters translate platform payloads to and from one universal
  `Message`
- extensions enrich or filter messages without changing delivery guarantees

The kernel stays transport-only.

## Current Focus

This slice establishes the new base core:

- one universal `Message`
- one adapter contract
- capability and lifecycle types
- kernel event model
- minimal exchange skeleton

Not implemented yet:

- storage backends
- full receive/store/forward pipeline
- instance manager
- router / ASGI
- CLI
- extensions
- real adapters

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
