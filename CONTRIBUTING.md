# Contributing

## Goals

This project accepts contributions that strengthen the messaging kernel,
adapter contracts, durability model, or developer ergonomics.

The main engineering rule is simple:

- transport concerns belong in the kernel
- content transformation belongs in extensions
- agent behavior belongs outside `unigate`

If a proposed change blurs that boundary, it should be challenged early.

## Development Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]
pytest
ruff check .
mypy src
```

## Expected Standards

- Python 3.11+
- type hints for public contracts
- tests for behavior changes
- no hidden special cases for one deployment mode
- no channel-specific logic inside the generic kernel path
- durable-state changes should be explicit and documented

## Contribution Areas

- core kernel contracts and state machines
- in-memory and SQLite backends
- testing utilities and fixtures
- first-party channel adapters
- first-party extensions
- documentation and examples

## Pull Request Expectations

- Keep changes scoped to one concern when possible.
- Update documentation when public behavior changes.
- Add or adjust tests with each kernel-level behavior change.
- Preserve backward compatibility within a major version unless an intentional
  breaking change is documented.

## Architectural Guardrails

- `UniversalMessage` and `OutboundMessage` are kernel contracts, not channel
  escape hatches.
- Built-in adapters may extend through metadata, but the core envelope should
  remain transport-neutral.
- Embedded mode, standalone mode, and MCP access should reuse the same kernel
  primitives rather than drift into separate implementations.

## Security

Do not open public issues for security-sensitive vulnerabilities. Use GitHub
Security Advisories or contact the maintainers privately.
