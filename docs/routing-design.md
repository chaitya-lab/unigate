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
              Extensions (transform/message hooks)
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

## Routing Configuration

### Location

Routing rules can be defined in:

1. **Main config file** - Inline under `routing:` key
2. **Separate file** - Referenced via `rules_file:` path
3. **Multiple files** - Via `include:` directive

```yaml
# Option 1: Inline in main config
# unigate.yaml
unigate:
  default_instance: unprocessed

routing:
  enabled: true
  default_action: keep
  rules_file: ./config/routing/rules.yaml  # Optional: external file
  rules:
    - name: "Email to Telegram"
      priority: 100
      match:
        from_channel: email
      actions:
        extensions:
          - email_subject_only
          - truncate_160
        forward_to:
          - telegram
```

### Routing Config File

```yaml
# config/routing/rules.yaml
routing:
  - name: "Email to Telegram"
    priority: 100
    enabled: true
    match:
      from_channel: email
      sender_pattern: "*@company.com"
    actions:
      extensions:
        - email_subject_only
        - truncate_160
      forward_to:
        - telegram
        - handler
      keep_in_default: false

  - name: "Support group"
    priority: 50
    match:
      from_channel: telegram
      group_id_pattern: "support-*"
    actions:
      extensions: []  # No transformation
      forward_to:
        - handler
        - email_archive
```
  
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

Extensions transform message content before forwarding. They receive a `Message` and return a (possibly modified) `Message`.

**Key Points:**
- Extensions are ordered - executed in the order specified
- One extension can have multiple transforms
- All transforms receive `Message` and return `Message`
- Extensions work on the unified `Message` format (channel-specific data in `raw` and `metadata`)

### Extension Types

1. **transform** - Modify message content
2. **filter** - Decide whether to continue (return None to drop)
3. **enrich** - Add metadata, tags, etc.

### Extension Definition

```yaml
extensions:
  # Extension with multiple transforms
  - name: email_processor
    type: transform
    transforms:
      - name: extract_subject
        # Extract email subject to message text
        code: |
          msg.text = msg.metadata.get("subject", "")
          
      - name: clean_html
        # Remove HTML from body
        code: |
          import re
          if msg.metadata.get("is_html"):
            msg.text = re.sub(r'<[^>]+>', '', msg.text or "")
    
  # Simple single-transform extension
  - name: truncate_160
    type: transform
    transforms:
      - name: truncate
        config:
          max_length: 160
          suffix: "..."
        code: |
          if msg.text and len(msg.text) > 160:
            msg.text = msg.text[:157] + "..."
```

### Built-in Extension Transforms

```yaml
extensions:
  # Email: Extract subject only, discard body
  - name: email_subject_only
    type: transform
    transforms:
      - name: extract_subject
        code: |
          subject = msg.metadata.get("subject", "")
          original_body = msg.text
          msg.text = subject if subject else "(no subject)"
          msg.metadata["original_body"] = original_body
    
  # SMS: Truncate to 160 chars
  - name: truncate_160
    type: transform
    transforms:
      - name: truncate
        code: |
          if msg.text and len(msg.text) > 160:
            msg.text = msg.text[:157] + "..."
    
  # Image: Convert to thumbnail URL
  - name: image_to_thumbnail
    type: transform
    transforms:
      - name: convert_thumbnail
        code: |
          if msg.media:
            for m in msg.media:
              if m.type == "image" and m.full_url:
                m.metadata["thumbnail"] = f"{m.full_url}?thumb=1"
    
  # Extract pattern to metadata
  - name: extract_order_id
    type: transform
    transforms:
      - name: extract
        config:
          pattern: "Order #(\\d+)"
          group: 1
          metadata_key: "order_id"
        code: |
          import re
          if msg.text:
            match = re.search(config["pattern"], msg.text)
            if match:
              msg.metadata["order_id"] = match.group(1)
```

### Custom Extension (Python)

```python
# extensions/my_transforms.py
from unigate import Message

class MyExtension:
    name = "my_transforms"
    type = "transform"
    
    def transforms(self):
        return [
            {"name": "add_prefix", "code": self.add_prefix},
            {"name": "add_sender", "code": self.add_sender},
        ]
    
    async def add_prefix(self, msg: Message, config: dict) -> Message:
        msg.text = f"[From {msg.sender.name}] {msg.text}"
        return msg
    
    async def add_sender(self, msg: Message, config: dict) -> Message:
        msg.metadata["routed_at"] = datetime.now().isoformat()
        return msg
```

### Extension Chaining

Extensions are executed in order. Each receives the output of the previous:

```yaml
actions:
  extensions:
    - email_subject_only    # Step 1: Extract subject
    - truncate_160         # Step 2: Truncate if needed
    - add_timestamp        # Step 3: Add timestamp
    - add_tags             # Step 4: Add metadata tags
```

The result is a pipeline: `Message → Extension1 → Extension2 → Extension3 → Message`

---

## Configuration Files

### Single File (Simple Setup)

```yaml
# unigate.yaml
unigate:
  default_instance: unprocessed
  mount_prefix: /unigate

instances:
  telegram:
    type: telegram
    token: !env:TELEGRAM_TOKEN
    
  email:
    type: email
    
  whatsapp:
    type: whatsapp
    
  handler:
    type: handler
    
  unprocessed:
    type: internal

# Routing rules inline
routing:
  default_action: keep
  unprocessed:
    instance: unprocessed
    retention_days: 7
    
  rules:
    - name: "Email to Telegram"
      priority: 100
      enabled: true
      match:
        from_channel: email
        sender_pattern: "*@company.com"
      actions:
        extensions:
          - email_subject_only
          - truncate_160
        forward_to:
          - telegram
          - handler

extensions:
  - name: email_subject_only
    type: transform
    transforms:
      - name: extract_subject
        code: |
          subject = msg.metadata.get("subject", "")
          msg.text = subject if subject else "(no subject)"
  - name: truncate_160
    type: transform
    transforms:
      - name: truncate
        code: |
          if msg.text and len(msg.text) > 160:
            msg.text = msg.text[:157] + "..."
```

### Multiple Files (Complex Setup)

```
config/
├── unigate.yaml          # Main config (references other files)
├── instances/
│   ├── telegram.yaml
│   ├── email.yaml
│   └── whatsapp.yaml
├── routing/
│   ├── rules.yaml        # Main routing rules
│   ├── customer_rules.yaml
│   └── priority_rules.yaml
└── extensions/
    ├── custom_transforms.py
    └── webhook_hook.py
```

```yaml
# unigate.yaml
unigate:
  default_instance: unprocessed

instances:
  # ... instance configs

routing:
  # Load rules from external files
  rules_file: ./config/routing/rules.yaml

extensions:
  # Built-in extensions
  - name: email_subject_only
    type: transform
    transforms:
      - name: extract
        code: |
          msg.text = msg.metadata.get("subject", "(no subject)")
  
  # Custom extension from Python file
  - name: my_transforms
    type: transform
    module: extensions.my_transforms
```

```yaml
# config/routing/rules.yaml
rules:
  # VIP customers: Email → Telegram + Handler
  - name: vip_email
    priority: 10
    match:
      from_channel: email
      sender_pattern: "*@vip.customer.com"
    actions:
      extensions:
        - email_subject_only
      forward_to:
        - telegram
        - handler
      
  # Support group: Telegram → Handler
  - name: support_group
    priority: 20
    match:
      from_channel: telegram
      group_id_pattern: "support-*"
    actions:
      extensions: []
      forward_to:
        - handler
      
  # Alerts: WhatsApp → SMS (truncated)
  - name: alert_sms
    priority: 30
    match:
      from_channel: whatsapp
      text_contains: "ALERT"
    actions:
      extensions:
        - truncate_160
      forward_to:
        - sms
        
  # Catch all: Keep for review
  - name: catch_all
    priority: 1000
    match: {}  # Matches everything
    actions:
      keep_in_default: true
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
   - Apply extensions (in order)
   - Forward to destinations

3. **Rule storage**
   - Load from YAML/JSON files
   - Runtime reload support (optional)

4. **Default instance handling**
   - Messages not matching rules → default instance
   - Retention policies for unprocessed

5. **Extension system updates**
   - New extension type: `transform`
   - Support for multiple transforms per extension
   - Transforms receive Message, return Message

### Files to Create/Modify

```
src/unigate/
├── routing/
│   ├── __init__.py
│   ├── engine.py        # Routing engine
│   ├── rule.py         # Rule definition
│   ├── matcher.py      # Match condition evaluation
│   └── executor.py     # Execute extensions
├── kernel.py           # Add routing integration
├── gate.py            # Remove fixed handler, add routing config
├── extensions.py       # Add transform type, multi-transform support
└── message.py         # Potentially add metadata fields
```

### Backward Compatibility

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

---

## Examples

### Example 1: Simple Email to Telegram

```yaml
routing:
  rules:
    - name: email_to_telegram
      priority: 100
      match:
        from_channel: email
      actions:
        extensions:
          - email_subject_only
        forward_to:
          - telegram

extensions:
  - name: email_subject_only
    type: transform
    transforms:
      - name: extract_subject
        code: |
          msg.text = f"[Email] {msg.metadata.get('subject', '')}"
```

### Example 2: Multi-channel Broadcast

```yaml
routing:
  rules:
    - name: announcement
      priority: 50
      match:
        from_channel: telegram
        group_id: "announcements"
      actions:
        extensions: []
        forward_to:
          - telegram
          - whatsapp
          - email
```

### Example 3: Content-based Routing

```yaml
routing:
  rules:
    - name: urgent_to_sms
      priority: 10
      match:
        text_contains: "URGENT"
      actions:
        extensions:
          - truncate_160
        forward_to:
          - sms
          
    - name: order_to_handler
      priority: 20
      match:
        text_pattern: "order.*\\d+"
      actions:
        extensions:
          - extract_order_id
          - add_timestamp
        forward_to:
          - handler
```

### Example 4: Conditional Routing with Multiple Extensions

```yaml
routing:
  rules:
    - name: email_support
      priority: 100
      match:
        from_channel: email
        sender_pattern: "*@support.com"
      actions:
        extensions:
          - email_subject_only       # Step 1: Extract subject
          - clean_special_chars      # Step 2: Clean text
          - add_support_tag         # Step 3: Add metadata
        forward_to:
          - handler
          - email_archive
```
