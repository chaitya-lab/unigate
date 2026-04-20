# Routing Configuration

UniGate routes messages using configurable rules. Rules are evaluated in priority order - first match wins.

---

## Quick Reference

```yaml
routing:
  default_action: keep      # keep | discard | forward
  rules:
    - name: rule-name      # Unique name (required)
      priority: 100        # Lower = higher priority (checked first)
      enabled: true        # Can disable without deleting
      match:              # Match conditions (see below)
      actions:            # What to do (see below)
```

---

## Match Syntax

UniGate supports **three** ways to match messages:

### 1. Simple Match (Key-Value)

Best for: Simple conditions, AND logic

```yaml
match:
  from_instance: telegram      # Source channel
  sender_id: "123456789"      # Exact sender ID
  text_contains: "urgent"   # Text contains word
```

All conditions must match (AND logic).

**Available fields:**

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `from_instance` | string | Source instance | `telegram` |
| `sender_id` | string | Sender ID | `"123456"` |
| `sender_pattern` | string | Glob pattern | `"vip_*"` |
| `sender_name_contains` | string | Name contains | `"John"` |
| `text_contains` | string | Text contains | `"help"` |
| `text_pattern` | string | Regex | `"^\\d{4}$"` |
| `group_id` | string | Group ID | `"chat123"` |
| `thread_id` | string | Thread ID | `"thread123"` |
| `has_media` | bool | Has media | `true` |
| `has_attachment` | bool | Has attachment | `true` |
| `has_image` | bool | Has image | `true` |
| `has_video` | bool | Has video | `true` |
| `day_of_week` | string/list | Day | `monday` or `[monday,tuesday]` |
| `hour_of_day` | int/list | Hour 0-23 | `9` or `[9,10,11]` |

---

### 2. Type-Based Match (Operations)

Best for: Complex conditions, multiple operations on same field

```yaml
match:
  - type: sender_id
    op: in
    value: ["123", "456", "789"]     # Multiple values (OR)
  
  - type: text
    op: contains
    value: "urgent"                 # Contains substring
  
  - type: group_id
    op: startswith
    value: "support-"              # Starts with
```

**Operators:**

| Operator | Description | Example Value |
|----------|-------------|---------------|
| `eq` | Equal | `"123"` |
| `ne` | Not equal | `"123"` |
| `contains` | Contains | `"urgent"` |
| `startswith` | Starts with | `"vip_"` |
| `endswith` | Ends with | `"_admin"` |
| `in` | In list | `["a","b","c"]` |
| `regex` | Regex pattern | `"^\\d{4}$"` |
| `gt` | Greater than | `100` |
| `lt` | Less than | `50` |
| `exists` | Field exists | `true` |

**Type names** (any message field):
- `sender_id`, `sender.name`, `sender.handle`
- `text`, `session_id`, `group_id`, `thread_id`
- `metadata.key` → `metadata.key` → accesses `msg.metadata.get('key')`
- `raw.field` → accesses raw field

---

### 3. Code Match (Python Expression)

Best for: Maximum flexibility, complex logic

```yaml
match:
  code: "msg.sender.platform_id == '123' or 'urgent' in (msg.text or '')"
```

**Access fields:**
- `msg.sender.platform_id` - Sender ID
- `msg.sender.name` - Sender name  
- `msg.text` - Message text
- `msg.metadata.get('key')` - Metadata value
- `msg.raw.get('field')` - Raw field
- `msg.group_id`, `msg.session_id`, etc.

**Available in code:**
- `msg` - Full Message object
- `config` - Rule config dict

---

## Actions

```yaml
actions:
  forward_to: [instance1, instance2]   # Send to destination(s)
  keep_in_default: true                  # Also keep in source (optional)
  extensions: [ext1, ext2]              # Transforms to apply
  add_tags: [tag1, tag2]                # Tags for tracking
```

- `forward_to`: One or more instances (fan-out = multiple destinations)
- `keep_in_default`: Keep message in original instance too
- `extensions`: Transform names to apply
- `add_tags`: Tags added to message metadata

---

## Examples

### Example 1: Route by User (Simple)

```yaml
routing:
  rules:
    - name: premium-user
      priority: 50
      match:
        from_instance: telegram
        sender_id: "123456789"      # Exact user ID
      actions:
        forward_to: [web_premium]
        extensions: [uppercase]

    - name: regular-user
      priority: 100
      match:
        from_instance: telegram
        sender_id: "987654321"
      actions:
        forward_to: [web_regular]

    - name: others
      priority: 200
      match:
        from_instance: telegram
      actions:
        forward_to: [web_default]
```

### Example 2: Route by User Group (Type-Based OR)

```yaml
routing:
  rules:
    - name: vip-users
      priority: 50
      match:
        - type: sender_id
          op: in
          value: ["123", "456", "789", "111"]
        - type: sender_id
          op: startswith
          value: "vip_"
      actions:
        forward_to: [vip_channel]

    - name: regular
      priority: 100
      match:
        from_instance: telegram
      actions:
        forward_to: [regular_channel]
```

### Example 3: Route by Text + Sender (Code)

```yaml
routing:
  rules:
    - name: urgent-vip
      priority: 50
      match:
        code: "(msg.sender.platform_id in ['123','456'] or msg.sender.platform_id.startswith('vip_')) and 'urgent' in (msg.text or '')"
      actions:
        forward_to: [priority_queue]
        extensions: [uppercase]

    - name: normal
      priority: 100
      match:
        code: "msg.text and 'help' in msg.text"
      actions:
        forward_to: [support]
```

### Example 4: Route by Time (Simple)

```yaml
routing:
  rules:
    - name: business-hours
      priority: 50
      match:
        hour_of_day: [9, 10, 11, 12, 13, 14, 15, 16, 17]
        day_of_week: [monday, tuesday, wednesday, thursday, friday]
      actions:
        forward_to: [live_support]

    - name: after-hours
      priority: 100
      match: {}        # Match everything else
      actions:
        forward_to: [voicemail]
```

### Example 5: Route by Media (Simple)

```yaml
routing:
  rules:
    - name: has-images
      priority: 50
      match:
        has_image: true
      actions:
        forward_to: [image_handler]

    - name: has-video
      priority: 50
      match:
        has_video: true
      actions:
        forward_to: [video_handler]

    - name: text-only
      priority: 100
      match:
        from_instance: telegram
      actions:
        forward_to: [text_handler]
```

### Example 6: Multiple Rules (OR simulation)

```yaml
routing:
  rules:
    - name: user-123-only
      priority: 50
      match:
        sender_id: "123"
      actions:
        forward_to: [dest_a]

    - name: user-456-only
      priority: 50
      match:
        sender_id: "456"
      actions:
        forward_to: [dest_b]

    - name: user-789-only  
      priority: 50
      match:
        sender_id: "789"
      actions:
        forward_to: [dest_c]

    - name: everyone-else
      priority: 200
      match: {}
      actions:
        forward_to: [dest_default]
```

First matching rule wins. Use priority to control order.

---

## Default Action

When no rule matches:

```yaml
routing:
  default_action: keep      # Keep in original instance (default)
  # default_action: discard  # Drop the message
  # default_action: forward  # Forward to default instances
  # default_forward_to: [archive]  # Used when default_action is forward
```

---

## Priority

**Lower number = higher priority**

```yaml
- name: urgent-rule
  priority: 1           # Checked FIRST
  match:
    text_contains: "urgent"
  actions:
    forward_to: [priority]

- name: normal-rule
  priority: 100          # Checked SECOND
  match:
    text_contains: "help"
  actions:
    forward_to: [support]

- name: default          # LAST RESORT
  priority: 1000
  match: {}
  actions:
    forward_to: [catchall]
```

"urgent help request" → routes to `priority` only (first match wins).

---

## Enable/Disable Rules

Disable without deleting:

```yaml
- name: temporary-disabled-rule
  enabled: false           # Rule ignored
  match:
    sender_id: "123"
  actions:
    forward_to: [dest]
```

---

## Testing Rules

```bash
# Validate config
python -m unigate start -f -c config.yaml

# Check loaded rules
python -m unigate status
```

---

## Message Fields Reference

```
Message:
  id                  # Unique message ID
  session_id          # Conversation ID
  from_instance       # Source channel name
  sender.platform_id  # Sender's platform ID
  sender.name         # Sender's display name
  sender.handle       # Sender's handle/username
  text                # Message text
  media               # List of media
  group_id            # Group ID (if in group)
  thread_id           # Thread ID
  metadata            # Custom metadata dict
  raw                  # Original platform payload
  ts                   # Timestamp
```

Access in code: `msg.sender.platform_id`, `msg.text`, `msg.metadata.get('key')`, etc.