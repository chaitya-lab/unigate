"""Web channel with built-in UI for testing."""

from __future__ import annotations

import asyncio
import json
import secrets
from typing import Any, ClassVar
from uuid import uuid4

from ..capabilities import ChannelCapabilities
from ..channel import BaseChannel, RawRequest, SendResult
from ..events import KernelEvent
from ..lifecycle import HealthStatus, SetupResult, SetupStatus
from ..message import Action, Interactive, InteractiveResponse, InteractionType, Message, Sender
from ..stores import SecureStore


HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Unigate Web - {instance_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #1a1a2e; color: #eee; }}
        .container {{ max-width: 800px; margin: 0 auto; }}
        h1 {{ color: #00d4ff; }}
        .chat {{ 
            border: 1px solid #333; 
            border-radius: 8px; 
            height: 400px; 
            overflow-y: auto; 
            padding: 15px; 
            background: #16213e;
            margin-bottom: 15px;
        }}
        .message {{ margin: 10px 0; padding: 10px; border-radius: 8px; }}
        .incoming {{ background: #0f3460; margin-right: 50px; }}
        .outgoing {{ background: #533483; margin-left: 50px; text-align: right; }}
        .sender {{ font-weight: bold; color: #00d4ff; font-size: 0.9em; }}
        .time {{ font-size: 0.7em; color: #888; }}
        .input-area {{ display: flex; gap: 10px; }}
        input {{ 
            flex: 1; 
            padding: 12px; 
            border: 1px solid #333; 
            border-radius: 8px; 
            background: #16213e; 
            color: #fff;
        }}
        button {{ 
            padding: 12px 24px; 
            background: #00d4ff; 
            border: none; 
            border-radius: 8px; 
            cursor: pointer;
            font-weight: bold;
        }}
        button:hover {{ background: #00a8cc; }}
        .interactive {{ 
            margin-top: 10px; 
            padding: 15px; 
            background: #1a1a2e; 
            border-radius: 8px;
        }}
        .interactive button {{ 
            margin: 5px; 
            min-width: 80px;
        }}
        .status {{ color: #4caf50; margin-bottom: 10px; }}
        .group-badge {{ background: #ff9800; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; }}
        pre {{ background: #0d1b2a; padding: 10px; border-radius: 4px; overflow-x: auto; font-size: 0.8em; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Unigate Web - {instance_id}</h1>
        <div class="status" id="status">Connecting...</div>
        
        <div class="chat" id="chat"></div>
        
        <div class="input-area">
            <input type="text" id="message" placeholder="Type a message..." onkeypress="if(event.key==='Enter')sendMessage()">
            <button onclick="sendMessage()">Send</button>
            <button onclick="sendInteractive()" style="background:#ff9800;">Interactive</button>
            <button onclick="sendGroup()" style="background:#9c27b0;">Group</button>
        </div>
        
        <details style="margin-top:20px;">
            <summary>Debug Info</summary>
            <pre id="debug"></pre>
        </details>
    </div>
    
    <script>
        const instanceId = "{instance_id}";
        const webPath = "{web_path}";
        const sessionId = localStorage.getInstanceId || (localStorage.setInstanceId = "{session_id}");
        let lastPoll = 0;
        
        async function sendMessage() {{
            const input = document.getElementById('message');
            const text = input.value.trim();
            if (!text) return;
            input.value = '';
            
            await fetch(`${webPath}/send`, {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ text, session_id: sessionId }})
            }});
            poll();
        }}
        
        async function sendInteractive() {{
            await fetch(`${webPath}/send`, {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ 
                    text: 'Are you sure?',
                    session_id: sessionId,
                    interactive: {{
                        type: 'confirm',
                        prompt: 'Do you want to continue?',
                        options: ['yes', 'no'],
                        timeout_seconds: 60
                    }}
                }})
            }});
            poll();
        }}
        
        async function sendGroup() {{
            const text = prompt('Enter message for group:') || 'Hello from group!';
            await fetch(`${webPath}/send`, {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ 
                    text, 
                    session_id: sessionId,
                    group_id: 'test-group-1',
                    bot_mentioned: true
                }})
            }});
            poll();
        }}
        
        async function poll() {{
            try {{
                const res = await fetch(`${webPath}/poll?since=` + lastPoll);
                const data = await res.json();
                lastPoll = data.timestamp;
                
                data.messages.forEach(msg => {{
                    addMessage(msg);
                    if (msg.interactive && msg.interactive.options) {{
                        showInteractive(msg);
                    }}
                }});
                
                document.getElementById('status').textContent = `Connected | Messages: ` + data.messages.length;
            }} catch (e) {{
                document.getElementById('status').textContent = 'Error: ' + e.message;
            }}
        }}
        
        function addMessage(msg) {{
            const chat = document.getElementById('chat');
            const div = document.createElement('div');
            div.className = 'message ' + (msg.direction === 'incoming' ? 'incoming' : 'outgoing');
            
            let html = `<div class="sender">${{msg.sender_name}}${{msg.group_id ? ' <span class="group-badge">GROUP</span>' : ''}}</div>`;
            html += `<div>${{msg.text || '(no text)'}}</div>`;
            if (msg.interactive && msg.interactive.response) {{
                html += `<div style="color:#4caf50;font-size:0.8em;">Response: ${{msg.interactive.response.value}}</div>`;
            }}
            html += `<div class="time">${{new Date(msg.timestamp).toLocaleTimeString()}}</div>`;
            
            div.innerHTML = html;
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
            
            document.getElementById('debug').textContent = JSON.stringify(msg, null, 2);
        }}
        
        function showInteractive(msg) {{
            const chat = document.getElementById('chat');
            const div = document.createElement('div');
            div.className = 'message incoming interactive';
            div.innerHTML = `
                <div>{prompt}</div>
                <div style="margin-top:10px;">
                    ${{msg.interactive.options.map(opt => 
                        `<button onclick="respondInteractive('${{msg.id}}','${{opt}}')">${{opt}}</button>`
                    ).join('')}}
                </div>
            `.replace('{prompt}', msg.interactive.prompt);
            chat.appendChild(div);
        }}
        
        async function respondInteractive(messageId, value) {{
            await fetch(`${webPath}/send`, {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ 
                    text: 'Response: ' + value,
                    session_id: sessionId,
                    interactive_response: {{
                        interaction_id: messageId,
                        value: value
                    }}
                }})
            }});
            poll();
        }}
        
        // Start polling
        document.getElementById('status').textContent = 'Connected - Polling...';
        setInterval(poll, 1000);
        poll();
    </script>
</body>
</html>
"""


class WebUIChannel(BaseChannel):
    name: ClassVar[str] = "webui"
    type: ClassVar[str] = "channel"
    transport: ClassVar[str] = "http"
    auth_method: ClassVar[str] = "none"

    def __init__(
        self,
        instance_id: str,
        store: SecureStore,
        kernel: Any,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.instance_id = instance_id
        self.store = store
        self.kernel = kernel
        self.config = config or {}
        self._sent: list[Message] = []
        self._pending: list[dict[str, Any]] = []
        self._last_poll = 0.0

    async def setup(self) -> SetupResult:
        return SetupResult(status=SetupStatus.READY)

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    def to_message(self, raw: dict[str, Any]) -> Message:
        from datetime import datetime, timezone
        sender_data = raw.get("sender", {})
        if isinstance(sender_data, dict):
            sender = Sender(
                platform_id=str(sender_data.get("id", "user")),
                name=str(sender_data.get("name", "User")),
                handle=sender_data.get("username"),
                is_bot=sender_data.get("is_bot", False),
                raw=sender_data,
            )
        else:
            sender = Sender(
                platform_id=str(sender_data),
                name=str(sender_data),
            )
        
        interactive = None
        if raw.get("interactive"):
            i = raw["interactive"]
            interactive = Interactive(
                interaction_id=i.get("interaction_id", str(uuid4())),
                type=i.get("type", "confirm"),
                prompt=i.get("prompt", ""),
                options=i.get("options"),
                timeout_seconds=i.get("timeout_seconds"),
                context=i.get("context", {}),
            )
        
        return Message(
            id=raw.get("id", str(uuid4())),
            session_id=raw.get("session_id", str(uuid4())),
            from_instance=self.instance_id,
            sender=sender,
            ts=datetime.now(timezone.utc),
            platform_id=raw.get("platform_id"),
            to=[],
            thread_id=raw.get("thread_id"),
            group_id=raw.get("group_id"),
            receiver_id=raw.get("receiver_id"),
            bot_mentioned=raw.get("bot_mentioned", True),
            text=raw.get("text"),
            interactive=interactive,
            raw=raw,
            metadata={},
        )

    async def from_message(self, msg: Message) -> SendResult:
        self._sent.append(msg)
        self._pending.append({
            "id": msg.id,
            "text": msg.text,
            "sender_name": msg.sender.name,
            "direction": "outgoing",
            "timestamp": msg.ts.timestamp() if msg.ts else 0,
            "interactive": None,
            "group_id": msg.group_id,
        })
        if msg.interactive:
            self._pending[-1]["interactive"] = {
                "id": msg.interactive.interaction_id,
                "prompt": msg.interactive.prompt,
                "options": msg.interactive.options,
                "type": msg.interactive.type,
            }
        
        # Cap pending list to prevent memory leak
        if len(self._pending) > 200:
            self._pending = self._pending[-200:]
            
        return SendResult(success=True, provider_message_id=f"webui:{msg.id}")

    async def handle_web(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        path = scope.get("path", "")
        
        if path == "/" or path == "":
            await self._serve_ui(scope, receive, send)
        elif path.startswith("/send"):
            await self._handle_send(scope, receive, send)
        elif path.startswith("/poll"):
            await self._handle_poll(scope, receive, send)
        else:
            await self._404(send)

    async def _serve_ui(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        from datetime import datetime, timezone
        
        mount_prefix = self.config.get("mount_prefix", "/unigate")
        session_id = f"{self.instance_id}:web:{uuid4().hex[:8]}"
        web_path = f"{mount_prefix}/web/{self.instance_id}"
        
        class SafeDict(dict):
            def __getitem__(self, key):
                try:
                    return super().__getitem__(key)
                except KeyError:
                    return "{" + key + "}"
        
        html = HTML_TEMPLATE.format_map(SafeDict({
            "instance_id": self.instance_id,
            "session_id": session_id,
            "web_path": web_path,
        }))
        
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"text/html"]],
        })
        await send({
            "type": "http.response.body",
            "body": html.encode(),
        })

    async def _handle_send(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        body_bytes = b""
        while True:
            event = await receive()
            if event["type"] == "http.request":
                body_bytes += event.get("body", b"")
                if not event.get("more_body", False):
                    break
        
        raw = {}
        if body_bytes:
            try:
                raw = json.loads(body_bytes.decode())
            except json.JSONDecodeError:
                pass
        
        msg = self.to_message(raw)
        
        if raw.get("interactive_response"):
            ir = raw["interactive_response"]
            msg.interactive = Interactive(
                interaction_id=ir.get("interaction_id", ""),
                type="response",
                prompt="",
                response=InteractiveResponse(
                    interaction_id=ir.get("interaction_id", ""),
                    type="confirm",
                    value=ir.get("value", ""),
                    raw=ir,
                ),
            )
        
        if self.kernel:
            await self.kernel.ingest(self.instance_id, {
                "id": msg.id,
                "session_id": raw.get("session_id", msg.session_id),
                "from_instance": self.instance_id,
                "sender": {"id": "web-user", "name": "Web User"},
                "text": raw.get("text"),
                "group_id": raw.get("group_id"),
                "bot_mentioned": raw.get("bot_mentioned", True),
                "thread_id": raw.get("thread_id"),
                "interactive_response": raw.get("interactive_response"),
                "ts": raw.get("ts"),
            })
            await self.kernel.flush_all_outbox()
        
        self._pending.append({
            "id": msg.id,
            "text": raw.get("text"),
            "sender_name": "You",
            "direction": "outgoing",
            "timestamp": __import__('time').time(),
            "interactive": None,
            "group_id": raw.get("group_id"),
        })
        
        # Cap pending list
        if len(self._pending) > 200:
            self._pending = self._pending[-200:]
        
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"application/json"]],
        })
        await send({
            "type": "http.response.body",
            "body": json.dumps({"ok": True}).encode(),
        })

    async def _handle_poll(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        from datetime import datetime, timezone
        query = dict(q.split("=") for q in (scope.get("query_string", b"").decode().split("&")) if "=" in q)
        since = float(query.get("since", 0))
        
        new_messages = [m for m in self._pending if m["timestamp"] > since]
        
        response = {
            "messages": new_messages,
            "timestamp": datetime.now(timezone.utc).timestamp(),
        }
        
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"application/json"]],
        })
        await send({
            "type": "http.response.body",
            "body": json.dumps(response).encode(),
        })

    async def _404(self, send: Any) -> None:
        await send({
            "type": "http.response.start",
            "status": 404,
            "headers": [],
        })
        await send({
            "type": "http.response.body",
            "body": b"Not found",
        })

    async def verify_signature(self, request: RawRequest) -> bool:
        return True

    @property
    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(
            direction="bidirectional",
            supports_groups=True,
            supports_threads=True,
            supports_reply_to=True,
            supports_typing_indicator=True,
            supports_media_send=True,
            supported_interaction_types=["confirm", "select"],
            max_message_length=4096,
        )

    async def health_check(self) -> HealthCheckResult:
        from datetime import datetime, timezone
        return HealthCheckResult(
            status=HealthStatus.HEALTHY,
            message="WebUI is configured",
            last_check=datetime.now(timezone.utc),
            details={"running": True},
        )

    async def background_tasks(self) -> list[object]:
        return []
