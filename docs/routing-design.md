# Routing System Design

> **For implementation details and usage examples, see [routing.md](routing.md)**

This document covers the architectural design of the routing system.

---

## Overview

The routing system determines where messages go after they enter the exchange. It replaces the single fixed handler concept with configurable rules.

---

## Core Concepts

### Message Flow

```
Channel Instance → Exchange → Routing Engine → Destination Instance(s)
                               ↓
                          Extensions (transforms)
```

### Default Action

When no rule matches:

```yaml
routing:
  default_action: keep      # keep | discard | forward
```

---

## Routing Engine

Located in `src/unigate/routing.py`:

- `RoutingEngine` - Main engine
- `RoutingRule` - Single rule definition
- `MatchCondition` - Conditions to match
- `RuleMatcher` - Evaluates conditions

### Evaluation Order

1. Rules evaluated by priority (lower = higher priority)
2. First matching rule wins
3. No cascading to other rules

---

## Supported Match Syntaxes

### 1. Simple (Key-Value)

```yaml
match:
  from_instance: telegram
  sender_id: "123"
```

### 2. Type-Based (Operations)

```yaml
match:
  - type: sender_id
    op: in
    value: ["123", "456"]
```

### 3. Code (Python)

```yaml
match:
  code: "msg.sender.platform_id == '123'"
```

See [routing.md](routing.md) for complete documentation.

---

## Message Structure

See [routing.md](routing.md#message-fields-reference) for message fields reference.

---

## Extension System

Extensions transform messages before forwarding:

```yaml
actions:
  extensions: [uppercase, truncate_160]
```

See [configuration.md](configuration.md#extensions-section) for more.

---

## Implementation Files

```
src/unigate/
├── routing.py       # Main routing engine
├── kernel.py        # Routes messages through engine
├── gate.py          # Loads routing config
├── message.py      # Message dataclass
└── plugins/        # Matchers and transforms
```

---

## Backward Compatibility

Old style (still works):
```python
@gate.on_message
async def handle(msg):
    return Message(text="reply")
```

New style (routing):
```yaml
routing:
  rules:
    - match: {}
      forward_to: [handler]
```

The `handler` instance maps to your registered handler function.

---

## Design Notes

### Why Three Syntaxes?

1. **Simple** - Most common cases, easy to read
2. **Type-Based** - Complex conditions, multiple operations
3. **Code** - Maximum flexibility for advanced users

### Priority System

Lower number = higher priority (checked first). First match wins.

---

## API Reference

See source code in `src/unigate/routing.py` for complete API.

---

## Related Documentation

- [routing.md](routing.md) - User guide and examples
- [configuration.md](configuration.md) - Complete config reference
- [plugins.md](plugins.md) - Channel and transform plugins