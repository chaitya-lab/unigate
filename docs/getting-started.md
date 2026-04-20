# Getting Started

This guide walks you through setting up and using Unigate from scratch.

---

## Prerequisites

- Python 3.11+
- pip
- Basic understanding of messaging systems

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourrepo/unigate.git
cd unigate
```

### 2. Create Virtual Environment

```bash
# Linux/Mac
python -m venv .venv
source .venv/bin/activate

# Windows PowerShell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install

```bash
# Basic installation
pip install -e .

# With development dependencies
pip install -e ".[dev]"

# Run tests to verify
python -m pytest tests/ -v
```

---

## Quick Start: Web UI

The fastest way to test Unigate.

### 1. Create Config

```yaml
# unigate.yaml
unigate:
  mount_prefix: /unigate

instances:
  web:
    type: webui

routing:
  default_action: keep
```

### 2. Start Server

```bash
unigate start -f
```

You'll see:
```
Unigate Server
============================================================
  Config: unigate.yaml
  Server: http://0.0.0.0:8080/unigate/

Routes:
  GET  /unigate/status      - Status dashboard
  GET  /unigate/health     - Health check
  GET  /unigate/instances  - Instance list
  GET  /unigate/web/web    - Web UI
============================================================
Press Ctrl+C to stop
```

### 3. Open Web UI

Navigate to: `http://localhost:8080/unigate/web/web/`

You should see a chat interface. Type a message and click Send.

### 4. Add Response Handler

The Web UI works, but messages go nowhere. Add a handler:

```python
# handler.py
from unigate import Message

async def handle_message(msg: Message) -> Message:
    # Echo back with uppercase
    return Message(
        to=[],
        session_id=msg.session_id,
        text=msg.text.upper() if msg.text else "Hello!"
    )
```

Restart with handler:
```bash
# In background mode
unigate start --config unigate.yaml
```

---

## Tutorial 1: Telegram Bot

Connect a Telegram bot to receive and respond to messages.

### 1. Create Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot`
3. Follow prompts, get your bot token: `123456:ABCdefGHIjklMNOpqrSTU`

### 2. Update Config

```yaml
# unigate.yaml
unigate:
  mount_prefix: /unigate

instances:
  telegram_bot:
    type: telegram
    token: "123456:ABCdefGHIjklMNOpqrSTU"
    mode: polling

routing:
  default_action: keep
```

### 3. Start Server

```bash
unigate start -f
```

### 4. Test

1. Open Telegram
2. Find your bot by its username
3. Send `/start`
4. Bot should respond

### 5. Add Responses

```python
# handler.py
from unigate import Message

async def handle(msg: Message) -> Message:
    text = msg.text.lower() if msg.text else ""
    
    if "hello" in text:
        reply = "Hi there!"
    elif "help" in text:
        reply = "I'm here to help!"
    else:
        reply = f"You said: {msg.text}"
    
    return Message(
        to=[],
        session_id=msg.session_id,
        text=reply
    )
```

---

## Tutorial 2: Route Between Channels

Forward messages from Web UI to Telegram and vice versa.

### 1. Create Config with Two Channels

```yaml
# unigate.yaml
unigate:
  mount_prefix: /unigate

instances:
  web:
    type: webui
    
  telegram_bot:
    type: telegram
    token: !env:TELEGRAM_TOKEN
    mode: polling

routing:
  default_action: keep
  rules:
    # Forward all messages from web to telegram
    - name: web-to-telegram
      priority: 100
      match:
        from_instance: web
      actions:
        forward_to: [telegram_bot]
    
    # Forward all messages from telegram to web
    - name: telegram-to-web
      priority: 100
      match:
        from_instance: telegram_bot
      actions:
        forward_to: [web]
```

### 2. Start Server

```bash
unigate start -f
```

### 3. Test

1. Open Web UI: `http://localhost:8080/unigate/web/web/`
2. Send a message
3. Check your Telegram bot - message appears there
4. Reply from Telegram
5. Check Web UI - reply appears there

---

## Tutorial 3: Content-Based Routing

Route messages based on their content.

### Config

```yaml
# unigate.yaml
unigate:
  mount_prefix: /unigate

instances:
  web:
    type: webui
    
  sales_telegram:
    type: telegram
    token: !env:SALES_TOKEN
    mode: polling
    
  support_telegram:
    type: telegram
    token: !env:SUPPORT_TOKEN
    mode: polling

routing:
  default_action: keep
  rules:
    # Messages containing "buy" go to sales
    - name: sales-inquiry
      priority: 50
      match:
        text_contains: "buy"
      actions:
        forward_to: [sales_telegram]
    
    # Messages containing "help" go to support
    - name: support-request
      priority: 50
      match:
        text_contains: "help"
      actions:
        forward_to: [support_telegram]
    
    # Everything else to sales as default
    - name: default-to-sales
      priority: 100
      match: {}
      actions:
        forward_to: [sales_telegram]
```

---

## Tutorial 4: Embedded in FastAPI

Mount Unigate into an existing FastAPI application. This is useful when you want to combine Unigate with existing routes, middleware, or authentication.

### 1. Create FastAPI App

```python
# myapp/main.py
from fastapi import FastAPI
from unigate import Unigate

app = FastAPI(title="MyApp")

# Mount unigate
gate = Unigate.from_config("unigate.yaml")
gate.mount_to_app(app, prefix="/unigate")

@app.get("/")
async def root():
    return {"message": "MyApp with Unigate"}

@app.get("/about")
async def about():
    return {
        "app": "MyApp",
        "unigate_routes": [
            "/unigate/status",
            "/unigate/web/web/",
            "/unigate/webhook/web/"
        ]
    }
```

### 2. Create Unigate Config

```yaml
# unigate.yaml
unigate:
  mount_prefix: /unigate

instances:
  web:
    type: webui

routing:
  default_action: keep
```

### 3. Run

```bash
# Terminal 1: Run your app
uvicorn myapp.main:app --port 8000

# Terminal 2: Start unigate instances
cd myapp
unigate start --config unigate.yaml
```

### 4. Access

- App: `http://localhost:8000/`
- Unigate Status: `http://localhost:8000/unigate/status`
- Web UI: `http://localhost:8000/unigate/web/web/`

---

## Tutorial 4b: Adding Authentication to Embedded Unigate

When embedding Unigate in another app, you may want to protect the management routes while allowing webhooks through. Here's how to add token authentication:

### 1. FastAPI App with Token Auth

```python
# myapp/main.py
import os
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from unigate import Unigate

app = FastAPI(title="MyApp")


class TokenAuthMiddleware(BaseHTTPMiddleware):
    """Guard Unigate routes with a token query parameter.
    
    Usage: Add ?token=YOUR_TOKEN to access protected routes
    """
    
    def __init__(self, app, token: str, paths: list[str] | None = None):
        super().__init__(app)
        self.token = token
        self.paths = paths or ["/unigate"]
    
    async def dispatch(self, request: Request, call):
        should_guard = any(request.url.path.startswith(p) for p in self.paths)
        
        if should_guard:
            # Allow webhooks through (they verify their own signatures)
            if request.url.path.startswith("/unigate/web/"):
                return await call(request)
            
            query_token = request.query_params.get("token")
            if query_token != self.token:
                return JSONResponse(
                    status_code=401,
                    content={"error": "Invalid or missing token"}
                )
        
        return await call(request)


# Load Unigate
gate = Unigate.from_config("unigate.yaml")

# Add auth middleware (get token from env)
app.add_middleware(
    TokenAuthMiddleware,
    token=os.getenv("UNIGATE_TOKEN", "secret123"),
    paths=["/unigate"]
)

# Mount Unigate
gate.mount_to_app(app, prefix="/unigate")
```

### 2. Using Protected Routes

```bash
# Without token - returns 401
curl http://localhost:8000/unigate/status

# With token - works
curl http://localhost:8000/unigate/status?token=secret123

# Webhook (no token needed) - works
curl -X POST http://localhost:8000/unigate/web/myinstance \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello"}'
```

### 3. Full Integration with Your App's Auth

You can also integrate with your existing authentication:

```python
from fastapi import Depends
from fastapi.security import HTTPBearer

security = HTTPBearer()

class MyAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call):
        should_guard = any(request.url.path.startswith(p) for p in ["/unigate"])
        
        if should_guard:
            # Skip auth for webhooks
            if request.url.path.startswith("/unigate/web/"):
                return await call(request)
            
            # Use your existing auth logic
            # e.g., check session, JWT, API key, etc.
            if not is_authenticated(request):
                return JSONResponse(status_code=401, content={"error": "Unauthorized"})
        
        return await call(request)
```

### 4. Adding Custom Message Handlers

You can also add handlers when embedding:

```python
from unigate import Unigate, Message

gate = Unigate.from_config("unigate.yaml")

@gate.on_message
async def handle_message(msg: Message) -> Message:
    """Process every message that passes through Unigate."""
    print(f"Got message: {msg.text}")
    return msg  # Continue routing

@gate.on_event("health.degraded")
async def handle_degraded(event):
    """Handle instance health events."""
    print(f"Instance degraded: {event.payload}")

gate.mount_to_app(app, prefix="/unigate")
```

### 5. Full Example: Complete FastAPI App

```python
# myapp/main.py
import os
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from unigate import Unigate, Message

app = FastAPI(title="MyApp")


class TokenAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, token: str, paths: list[str] | None = None):
        super().__init__(app)
        self.token = token
        self.paths = paths or ["/unigate"]
    
    async def dispatch(self, request: Request, call):
        should_guard = any(request.url.path.startswith(p) for p in self.paths)
        
        if should_guard:
            if request.url.path.startswith("/unigate/web/"):
                return await call(request)
            if request.query_params.get("token") != self.token:
                return JSONResponse(status_code=401, content={"error": "Unauthorized"})
        
        return await call(request)


# Load Unigate
gate = Unigate.from_config("unigate.yaml")

# Add message handler
@gate.on_message
async def process_message(msg: Message) -> Message:
    # Your custom logic here
    if "help" in (msg.text or "").lower():
        msg.metadata["auto_reply"] = True
    return msg

# Add auth middleware
app.add_middleware(
    TokenAuthMiddleware,
    token=os.getenv("UNIGATE_TOKEN", "secret"),
    paths=["/unigate"]
)

# Mount
gate.mount_to_app(app, prefix="/unigate")
```

---

## Tutorial 5: Webhook Channel

Receive messages from external services via webhook.

### 1. Create Config

```yaml
# unigate.yaml
unigate:
  mount_prefix: /unigate

instances:
  # Your service sends to this webhook
  webhook:
    type: web
    auth_method: hmac
    secret: "my-webhook-secret"
    
  # Forward to Telegram
  telegram_bot:
    type: telegram
    token: !env:TELEGRAM_TOKEN
    mode: polling

routing:
  default_action: keep
  rules:
    - name: webhook-to-telegram
      priority: 100
      match:
        from_instance: webhook
      actions:
        forward_to: [telegram_bot]
```

### 2. Send Webhook

```bash
curl -X POST http://localhost:8080/unigate/webhook/web \
  -H "Content-Type: application/json" \
  -H "X-Signature: <computed-signature>" \
  -d '{
    "text": "Hello from webhook!",
    "sender": {"id": "user123", "name": "Webhook User"}
  }'
```

---

## Tutorial 6: Using the CLI

Manage your running Unigate instance.

### With Daemon Running

```bash
# Check status
unigate status

# List instances
unigate instances list

# View inbox
unigate inbox list

# View outbox
unigate outbox list

# Check health
unigate health

# View logs
unigate logs --limit 50
```

### View Specific Message

```bash
# Get message ID from inbox list
unigate inbox show msg_abc123
```

### Replay Failed Message

```bash
unigate inbox replay msg_abc123
```

### View Dead Letters

```bash
# List failed messages
unigate dead-letters list

# Show details
unigate dead-letters show dl_xyz789

# Requeue for retry
unigate dead-letters requeue dl_xyz789
```

---

## Tutorial 7: Multiple Matchers

Combine conditions for complex routing.

### Config

```yaml
routing:
  rules:
    # VIP users during business hours
    - name: vip-business-hours
      priority: 10
      match:
        sender_pattern: "vip_*"
        hour_of_day: [9, 10, 11, 12, 13, 14, 15, 16, 17]
        day_of_week: ["monday", "tuesday", "wednesday", "thursday", "friday"]
      actions:
        forward_to: [vip_telegram]
    
    # Regular users on weekends
    - name: weekend-support
      priority: 20
      match:
        day_of_week: ["saturday", "sunday"]
      actions:
        forward_to: [weekend_telegram]
```

---

## Next Steps

- Read [Configuration Reference](configuration.md) for all options
- Read [Routing](routing.md) for routing rules
- Read [Plugins](plugins.md) to create custom channels
- Check [CLI Reference](cli.md) for all commands

---

## Troubleshooting

### Server won't start

```bash
# Check if port is in use
netstat -an | grep 8080

# Try different port
unigate start --port 9000
```

### Telegram not responding

1. Verify bot token is correct
2. Check token has no spaces
3. Try `/start` command directly in Telegram first

### Messages not routing

```bash
# Check inbox for messages
unigate inbox list

# Check routing rules in config
# Verify instance names match exactly
```

### Webhook signature failed

Verify the secret key matches in config and your webhook sender.

---

## Getting Help

- Check [Architecture](../architecture.md) for system design
- Open an issue on GitHub
- Check existing discussions
