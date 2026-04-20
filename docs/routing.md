# Routing Configuration

## Overview

Unigate routes messages based on configurable rules. Rules are defined in YAML and evaluated in priority order.

## Configuration

```yaml
# unigate.yaml
unigate:
  mount_prefix: /unigate

instances:
  web_ui:
    type: webui
  telegram_sales:
    type: telegram
    token: !env:TELEGRAM_TOKEN
  telegram_support:
    type: telegram
    token: !env:SUPPORT_TOKEN

routing:
  default_action: keep  # keep, discard, or forward
  default_instance: default
  unprocessed:
    retention_days: 7
  rules:
    - name: sales-keyword
      priority: 100
      enabled: true
      match:
        text_contains: "sales"
      actions:
        forward_to: [telegram_sales]
    
    - name: support-keyword
      priority: 100
      match:
        text_contains: "help"
      actions:
        forward_to: [telegram_support]
```

## Rule Structure

```yaml
routing:
  rules:
    - name: my-rule              # Required: unique name
      priority: 100             # Lower = higher priority (checked first)
      enabled: true             # Can be false to disable
      match:                    # Match conditions (three syntaxes below)
      actions:
        forward_to: [instance1, instance2]  # Where to send
        keep_in_default: false   # Also send to default destination
        add_tags: [tag1, tag2]  # Tags for tracking
        extensions: []          # Transforms to apply
```

## Match Syntax

UniGate supports three match syntaxes:

### 1. Simple (Key-Value)

```yaml
match:
  from_instance: web
  sender_id: "123456"
  text_contains: "urgent"
```

All conditions = AND logic (all must match).

### 2. Type-Based (List of Conditions)

```yaml
match:
  - type: sender_id
    op: in
    value: ["123", "456", "789"]
  - type: text
    op: contains
    value: "urgent"
```

**Operators:**
| Operator | Description | Example |
|----------|-------------|---------|
| `eq` | Equal | `value: "123"` |
| `ne` | Not equal | `value: "123"` |
| `contains` | Contains substring | `value: "urgent"` |
| `startswith` | Starts with | `value: "vip_"` |
| `endswith` | Ends with | `value: "_admin"` |
| `in` | In list | `value: ["a", "b", "c"]` |
| `regex` | Regex pattern | `value: "^\\d{4}$"` |
| `gt` | Greater than | `value: 100` |
| `lt` | Less than | `value: 50` |
| `exists` | Field exists | `value: true` |

**Field Types:** Use any message field (e.g., `sender_id`, `sender.name`, `metadata.key`, `raw.update_id`)

### 3. Code (Python Expression)

```yaml
match:
  code: "msg.sender.platform_id == '123' or 'urgent' in (msg.text or '')"
```

Available: `msg` (Message object), `msg.sender.platform_id`, `msg.text`, `msg.metadata`, etc.

## Match Conditions

| Condition | Type | Description | Example |
|-----------|------|-------------|---------|
| `from_instance` | string | Source channel instance | `web_ui` |
| `text_contains` | string | Text substring (case-insensitive) | `"sales"` |
| `text_pattern` | string | Regex pattern | `"\d{4}-\d{2}-\d{2}"` |
| `sender_id` | string | Exact sender ID | `"user123"` |
| `sender_pattern` | string | Glob pattern | `"vip_*"` |
| `sender_name_contains` | string | Name substring | `"John"` |
| `group_id` | string | Exact group ID | `"dev-channel"` |
| `group_id_pattern` | string | Glob pattern | `"dev-*" |
| `thread_id` | string | Thread ID | `"thread123"` |
| `has_media` | bool | Has any media | `true` |
| `has_attachment` | bool | Has attachment | `true` |
| `has_image` | bool | Has image | `true` |
| `has_video` | bool | Has video | `true` |
| `day_of_week` | string/list | Day name(s) | `monday` or `[monday, tuesday]` |
| `hour_of_day` | int/list | Hour(s) 0-23 | `9` or `[9, 10, 11]` |

## Priority

**Lower number = higher priority**

Rules are evaluated in priority order. The **first matching rule wins**.

```yaml
# Example: Urgent takes precedence
routing:
  rules:
    - name: urgent-high
      priority: 1              # Highest priority
      match:
        text_contains: "URGENT"
      actions:
        forward_to: [priority_channel]

    - name: normal
      priority: 100            # Normal priority
      match:
        text_contains: "help"
      actions:
        forward_to: [support_channel]
```

Message "URGENT help" → routes to `priority_channel` only.

## Actions

### forward_to

Send message to specified instance(s):

```yaml
actions:
  forward_to: [telegram_bot]
```

Multiple destinations (fan-out):
```yaml
actions:
  forward_to: [email, slack, pagerduty]
```

### keep_in_default

Forward to specified destination AND keep in default:

```yaml
actions:
  forward_to: [archive]
  keep_in_default: true
```

### add_tags

Add tags to message metadata:

```yaml
actions:
  forward_to: [handler]
  add_tags: [sales, qualified]
```

### extensions

Apply transforms before forwarding:

```yaml
actions:
  forward_to: [sms]
  extensions:
    - transform.truncate  # Max 160 chars for SMS
```

## Multiple Conditions (AND Logic)

All conditions must match for the rule to apply:

```yaml
- name: vip-dev-team
  priority: 10
  match:
    sender_pattern: "vip_*"      # AND
    group_id: "dev-team"         # AND
    hour_of_day: [9, 10, 11, 12, 13, 14, 15, 16, 17]  # AND
  actions:
    forward_to: [vip_dev_channel]
```

## Default Action

When no rule matches:

```yaml
routing:
  default_action: keep    # Keep in original instance
  # default_action: discard  # Drop the message
  # default_action: forward  # Forward to specific instances
  # default_forward_to: [archive]  # Used when default_action is forward
```

## Examples

### Route by Text Content

```yaml
routing:
  rules:
    - name: sales-messages
      priority: 100
      match:
        text_contains: "buy"
      actions:
        forward_to: [sales_telegram]

    - name: support-messages
      priority: 100
      match:
        text_contains: "help"
      actions:
        forward_to: [support_telegram]
```

### Route by Sender (One Bot, Multiple Users)

**The most common pattern: one Telegram bot, different users get different routing and transforms:**

```yaml
# One bot, different users -> different handling
routing:
  rules:
    # Premium user gets uppercase + VIP channel
    - name: premium-user
      priority: 50
      match:
        from_instance: telegram           # From the bot
        sender_id: "123456789"            # Premium user ID
      actions:
        forward_to: [web_premium]
        extensions:
          - uppercase
          - add_prefix

    # Regular user gets lowercase + regular channel
    - name: regular-user
      priority: 100
      match:
        from_instance: telegram
        sender_id: "987654321"            # Regular user ID
      actions:
        forward_to: [web_regular]
        extensions:
          - lowercase

    # Default for other users
    - name: catch-all
      priority: 200
      match:
        from_instance: telegram
      actions:
        forward_to: [web_standard]
```

**Using sender_pattern for groups of users:**

```yaml
routing:
  rules:
    # All VIP users (pattern matching)
    - name: vip-users
      priority: 50
      match:
        sender_pattern: "vip_*"            # Users with ID starting "vip_"
      actions:
        forward_to: [vip_channel]

    - name: regular-users
      priority: 100
      match: {}                           # Matches everything else
      actions:
        forward_to: [general_channel]
```

### Route by Group

```yaml
routing:
  rules:
    - name: engineering
      priority: 100
      match:
        group_id_pattern: "eng-*"
      actions:
        forward_to: [eng_slack]

    - name: sales-team
      priority: 100
      match:
        group_id_pattern: "sales-*"
      actions:
        forward_to: [sales_slack]
```

### Business Hours Routing

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
      match: {}
      actions:
        forward_to: [voicemail]
```

### Media Routing

```yaml
routing:
  rules:
    - name: image-attachments
      priority: 100
      match:
        has_image: true
      actions:
        forward_to: [image_processor]
        extensions:
          - transform.add_metadata
          - add_timestamp

    - name: video-content
      priority: 100
      match:
        has_video: true
      actions:
        forward_to: [video_processor]
```

## Viewing Rules

```bash
# List all routing rules
unigate plugins status
```

## Validating Rules

```bash
# Validate routing configuration
unigate plugins validate --config unigate.yaml
```

## Loading from External File

```yaml
routing:
  rules_file: ./config/routing/rules.yaml
```

```yaml
# config/routing/rules.yaml
rules:
  - name: external-rule
    priority: 100
    match:
      text_contains: "external"
    actions:
      forward_to: [external_handler]
```

## Complete Example

```yaml
unigate:
  mount_prefix: /unigate

instances:
  web_ui:
    type: webui

  telegram_sales:
    type: telegram
    token: !env:SALES_TOKEN

  telegram_support:
    type: telegram
    token: !env:SUPPORT_TOKEN

  sms_gateway:
    type: web
    webhook_secret: !env:SMS_SECRET

routing:
  default_action: keep
  
  rules:
    # VIP users go to priority queue
    - name: vip-routing
      priority: 10
      match:
        sender_pattern: "vip_*"
      actions:
        forward_to: [telegram_sales]
        add_tags: [vip]

    # Sales keywords to sales team
    - name: sales-keywords
      priority: 50
      match:
        text_contains: ["buy", "purchase", "pricing", "quote"]
      actions:
        forward_to: [telegram_sales]
        add_tags: [sales]

    # Support keywords to support team
    - name: support-keywords
      priority: 50
      match:
        text_contains: ["help", "support", "issue", "problem"]
      actions:
        forward_to: [telegram_support]
        add_tags: [support]

    # Media attachments to processor
    - name: media-attachment
      priority: 100
      match:
        has_attachment: true
      actions:
        forward_to: [sms_gateway]
        extensions:
          - transform.truncate

    # Everything else stays in web UI
    - name: catch-all
      priority: 1000
      match: {}
      actions:
        keep_in_default: true
```
