# Routing System Design

## Overview

The routing system determines where messages go after they enter the exchange. It replaces the single fixed handler concept with configurable rules.

---

## Core Concepts

### 1. Message Flow

```
Channel Instance → Exchange → Routing Engine → [Destination Instance(s)] → Channel Instance
                     ↓
              Routing Rules
                     ↓
              Extensions (optional transformations)
                     ↓
              Destination(s)
```

### 2. Default Instance

Every message that enters the exchange goes to a **default instance** unless routing rules match. This is like an "inbox" or "unprocessed" area.

```yaml
unigate:
  default_instance: unigate_inbox  # or "discard"
  
instances:
  unigate_inbox:
    type: internal  # Internal handler for unprocessed messages
```

**Options for default_instance:**
- `"discard"` - Drop messages that don't match any rule
- `"keep"` - Store in special "unprocessed" area (configurable retention)
- Instance ID - Forward unmatched messages to this instance

---

## Routing Rules

### Structure

```yaml
# routing/rules.yaml (or combined in unigate.yaml)
routing:
  enabled: true
  default_action: keep  # keep | discard | forward
  
rules:
  - name: "Email to Telegram"
    priority: 100  # Lower = higher priority
    enabled: true
    
    # Match conditions (all must match if multiple)
    match:
      from_channel: email
      sender_pattern: "*@company.com"  # Glob pattern
      # OR
      # sender_id: "specific@email.com"
      # subject_contains: "urgent"
    
    # Actions
    actions:
      # Transform content before forwarding (optional)
      transform:
        - extension: email_subject_only  # Use extension to extract subject
        - extension: truncate_160       # Truncate to 160 chars for SMS
        
      # Forward to these destinations
      forward_to:
        - telegram
        - sms
        
      # Also keep in default instance?
      keep_in_default: false
      
  - name: "Support group to handler"
    priority: 50
    match:
      from_channel: telegram
      group_id_pattern: "support-*"
      
    actions:
      forward_to:
        - handler  # Special "handler" instance
        - email_archive
      keep_in_default: false
      
  - name: "WhatsApp alerts to SMS"
    priority: 80
    match:
      from_channel: whatsapp
      text_contains: "alert"
      
    actions:
      transform:
        - extension: extract_alert_code
        - extension: truncate_160
      forward_to:
        - sms
```

### Match Conditions

```yaml
match:
  # Channel-based
  from_channel: email              # telegram, whatsapp, email, web, etc.
  from_instance: "support-telegram"  # Specific instance name
  
  # Sender-based
  sender_pattern: "*@company.com"  # Glob pattern
  sender_id: "user123"            # Exact match
  sender_name_contains: "John"
  
  # Content-based
  text_contains: "help"            # Case-insensitive
  text_pattern: "^/command.*"     # Regex
  subject_contains: "URGENT"      # Email subject
  
  # Context-based
  group_id_pattern: "support-*"   # Glob pattern
  thread_id: "thread-123"         # Exact match
  has_media: true                 # Has attachments
  
  # Combining conditions (AND logic)
  and:
    - text_contains: "order"
    - sender_pattern: "*@shop.com"
    
  # OR conditions
  or:
    - sender_pattern: "*@vip.com"
    - sender_pattern: "*@support.com"
```

### Actions

```yaml
actions:
  # Required: Where to forward
  forward_to:
    - telegram
    - sms
    - handler           # Special: goes to application handler
    - email_archive    # Any registered instance
    
  # Optional: Transform content first
  transform:
    - extension: email_subject_only
    - extension: truncate_160
    - extension: image_to_thumbnail
    
  # Optional: Keep in default instance too
  keep_in_default: false
  
  # Optional: Add metadata/tags
  add_tags:
    - customer_inquiry
    - priority_high
```

---

## Extensions for Content Transformation

Extensions can transform message content before forwarding. They receive a Message and return a (possibly modified) Message.

### Built-in Transformation Extensions

```yaml
extensions:
  - name: email_subject_only
    type: transform
    # Extracts subject from email, clears body
    
  - name: truncate_160
    type: transform
    config:
      max_length: 160
      suffix: "..."
      
  - name: image_to_thumbnail
    type: transform
    config:
      max_width: 640
      max_height: 480
      
  - name: extract_order_id
    type: transform
    config:
      pattern: "Order #(\d+)"
      extract_to_metadata: "order_id"
      
  - name: translate_to_english
    type: transform
    config:
      source_lang: auto
      target_lang: en
```

### Custom Transform Extension

```python
# extensions/extract_subject.py
from unigate import BaseExtension, Message

class ExtractSubjectExtension(BaseExtension):
    name = "email_subject_only"
    type = "transform"  # Mark as transform extension
    
    async def transform(self, msg: Message) -> Message:
        # Extract subject from email, set as text
        if msg.from_channel == "email":
            subject = msg.metadata.get("subject", "")
            return msg.model_copy(update={
                "text": f"[Subject] {subject}",
                "metadata": {**msg.metadata, "original_body": msg.text}
            })
        return msg
```

---

## Configuration Files

### Single File (Simple Setup)

```yaml
# unigate.yaml
unigate:
  default_instance: unigate_inbox

instances:
  telegram:
    type: telegram
    token: !env:TELEGRAM_TOKEN
    
  email:
    type: email
    # ...
    
  unigate_inbox:
    type: internal

routing:
  default_action: keep
  rules_file: ./routing/rules.yaml  # Optional external file

extensions:
  - name: email_subject_only
    type: transform
```

### Multiple Files (Complex Setup)

```
config/
├── unigate.yaml
├── instances/
│   ├── telegram.yaml
│   ├── email.yaml
│   └── whatsapp.yaml
└── routing/
    ├── rules.yaml          # Main routing rules
    ├── customer_rules.yaml # Customer-specific
    └── priority.yaml      # Override priorities
```

```yaml
# routing/rules.yaml
routing:
  - include: customer_rules.yaml
  - include: priority.yaml
  
  rules:
    # Inline rules here
```

---

## Message Retention (No Match)

When a message doesn't match any routing rule:

```yaml
routing:
  default_action: keep  # keep | discard | forward
  
  # If keep, where and how long
  unprocessed:
    instance: unigate_inbox
    retention_days: 30  # Auto-delete after 30 days
    
  # If discard, optional logging
  discard:
    log: true
    log_level: info
```

---

## Handler Instance (Special)

The `handler` is a special instance that represents your application code:

```yaml
instances:
  handler:
    type: handler
    # No channel config needed
    
routing:
  rules:
    - match:
        group_id_pattern: "support-*"
      actions:
        forward_to:
          - handler
```

```python
# app.py
from unigate import Unigate, Message

gate = Unigate.from_config("unigate.yaml")

@gate.on_message
async def handle(msg: Message) -> Message:
    # This is the "handler" instance
    return Message(
        session_id=msg.session_id,
        text=f"Echo: {msg.text}"
    )
```

---

## Example: Full Customer Support Setup

```yaml
# unigate.yaml
unigate:
  default_instance: unprocessed
  mount_prefix: /unigate

storage:
  backend: file
  path: ./data

instances:
  telegram_support:
    type: telegram
    token: !env:TELEGRAM_TOKEN
    
  whatsapp_business:
    type: whatsapp
    # ...
    
  email_support:
    type: email
    # ...
    
  sms_fallback:
    type: sms
    # ...
    
  handler:
    type: handler
    
  unprocessed:
    type: internal
    
routing:
  default_action: keep
  unprocessed:
    instance: unprocessed
    retention_days: 7

extensions:
  - name: email_subject_only
    type: transform
  - name: truncate_160
    type: transform
    config:
      max_length: 160

rules:
  # VIP customers: Email + Telegram + Handler
  - name: vip_email
    priority: 10
    match:
      from_channel: email
      sender_pattern: "*@vip.customer.com"
    actions:
      forward_to:
        - telegram_support
        - handler
        
  # Support group: Telegram → Handler + Archive
  - name: support_group
    priority: 20
    match:
      from_channel: telegram
      group_id_pattern: "support-*"
    actions:
      forward_to:
        - handler
        - email_archive
        
  # Alerts: WhatsApp → SMS (truncated)
  - name: alert_sms
    priority: 30
    match:
      from_channel: whatsapp
      text_contains: "ALERT"
    actions:
      transform:
        - email_subject_only
        - truncate_160
      forward_to:
        - sms_fallback
        
  # Default emails: Just to handler
  - name: default_email
    priority: 100
    match:
      from_channel: email
    actions:
      forward_to:
        - handler
        
  # All other messages: Keep for review
  - name: catch_all
    priority: 1000
    match: {}  # Matches everything
    actions:
      keep_in_default: true
```

---

## Event Hooks

Extensions can hook into routing events:

```yaml
extensions:
  - name: routing_logger
    type: event
    events:
      - routing.matched      # When rule matches
      - routing.no_match     # When no rule matches
      - routing.forwarded   # When message is forwarded
      
  - name: analytics
    type: event
    events:
      - routing.matched
    config:
      track_to: analytics_service
```

---

## Priority and Evaluation

1. Rules evaluated in priority order (lower = higher priority)
2. First matching rule wins (no cascading)
3. Multiple `forward_to` = broadcast to all
4. `keep_in_default` adds to default, doesn't prevent forward

```
Message arrives
    ↓
Evaluate rule priority: 10, 20, 30, 100, 1000
    ↓
Match rule priority: 20 (group_id_pattern: "support-*")
    ↓
Check match conditions → All match
    ↓
Run transformations (extensions)
    ↓
Forward to: [handler, email_archive]
    ↓
Done (no further rules evaluated)
```

---

## Error Handling

```yaml
routing:
  error_action: keep_in_default  # What if extension fails
  
  rules:
    - name: safe_rule
      match:
        from_channel: telegram
      actions:
        forward_to:
          - handler
        on_error:
          action: keep_in_default
          log_level: error
```

---

## Implementation Notes

### Core Changes Needed

1. **Remove fixed handler from gate.py**
   - Handler becomes just another instance type
   - `on_message` decorator registers handler instance

2. **Add routing engine to kernel**
   - Evaluate rules on inbound message
   - Apply transformations
   - Forward to destinations

3. **Rule storage**
   - Load from YAML/JSON files
   - Runtime reload support (optional)

4. **Default instance handling**
   - Messages not matching rules → default instance
   - Retention policies for unprocessed

5. **Transform extension type**
   - New extension type: `transform`
   - Sync or async transformation

### Files to Create/Modify

```
src/unigate/
├── routing/
│   ├── __init__.py
│   ├── engine.py        # Routing engine
│   ├── rule.py         # Rule definition
│   ├── matcher.py      # Match condition evaluation
│   └── transformer.py # Transform extensions
├── kernel.py           # Add routing integration
├── gate.py            # Remove fixed handler
└── extensions.py       # Add transform type
```

---

## Backward Compatibility

For existing users, provide migration path:

```python
# Old style (still works)
@gate.on_message
async def handle(msg):
    return Message(text="reply")

# New style
routing:
  rules:
    - match: {}
      forward_to: [handler]  # Handler as destination
```

The `handler` keyword in `forward_to` maps to the registered handler instance.
