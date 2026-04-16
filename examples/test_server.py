"""Test server combining Web UI and Telegram channels."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from unigate import Exchange, Message, NamespacedSecureStore, TelegramChannel
from unigate.channels import WebUIChannel
from unigate.stores import InMemoryStores


class UnifiedHandler:
    def __init__(self, exchange: Exchange, web_channel: WebUIChannel) -> None:
        self.exchange = exchange
        self.web_channel = web_channel
        self.interaction_count = 0
        self.sessions: dict[str, dict] = {}

    async def handle(self, msg: Message) -> Message | None:
        print(f"\n=== INCOMING from {msg.from_instance} ===")
        print(f"  Sender: {msg.sender.name} ({msg.sender.platform_id})")
        print(f"  Text: {msg.text}")
        print(f"  Session: {msg.session_id}")
        print(f"  Group: {msg.group_id}")
        print(f"  Thread: {msg.thread_id}")
        print(f"  Bot mentioned: {msg.bot_mentioned}")
        
        if msg.interactive and msg.interactive.response:
            print(f"  [INTERACTIVE RESPONSE] value={msg.interactive.response.value}")
            self.interaction_count += 1
            self.sessions[msg.session_id] = {
                "interactive_count": self.interaction_count,
                "last_response": msg.interactive.response.value,
            }
            return Message(
                id=f"reply-{datetime.now(timezone.utc).timestamp()}",
                session_id=msg.session_id,
                from_instance="handler",
                sender=msg.sender,
                ts=datetime.now(timezone.utc),
                text=f"Got your response: {msg.interactive.response.value} (Total: {self.interaction_count})",
            )
        
        if msg.text == "/test":
            return Message(
                id=f"reply-{datetime.now(timezone.utc).timestamp()}",
                session_id=msg.session_id,
                from_instance="handler",
                sender=msg.sender,
                ts=datetime.now(timezone.utc),
                text="Test OK! Try /interactive, /select, or /help",
            )
        
        if msg.text == "/interactive":
            return Message(
                id=f"reply-{datetime.now(timezone.utc).timestamp()}",
                session_id=msg.session_id,
                from_instance="handler",
                sender=msg.sender,
                ts=datetime.now(timezone.utc),
                text="Do you want to proceed?",
                interactive={
                    "type": "confirm",
                    "interaction_id": f"confirm-{datetime.now(timezone.utc).timestamp()}",
                    "prompt": "Do you want to proceed?",
                    "options": ["yes", "no"],
                    "timeout_seconds": 60,
                },
            )
        
        if msg.text == "/select":
            return Message(
                id=f"reply-{datetime.now(timezone.utc).timestamp()}",
                session_id=msg.session_id,
                from_instance="handler",
                sender=msg.sender,
                ts=datetime.now(timezone.utc),
                text="Choose an option:",
                interactive={
                    "type": "select",
                    "interaction_id": f"select-{datetime.now(timezone.utc).timestamp()}",
                    "prompt": "What would you like to do?",
                    "options": ["Option A", "Option B", "Option C", "Cancel"],
                    "timeout_seconds": 60,
                },
            )
        
        if msg.text == "/help":
            help_text = """
Available commands:
/test - Test message
/interactive - Send YES/NO confirm
/select - Send multi-choice select
/dump - Show session info
/help - Show this help
            """.strip()
            return Message(
                id=f"reply-{datetime.now(timezone.utc).timestamp()}",
                session_id=msg.session_id,
                from_instance="handler",
                sender=msg.sender,
                ts=datetime.now(timezone.utc),
                text=help_text,
            )
        
        if msg.text == "/dump":
            sess = self.sessions.get(msg.session_id, {})
            dump = f"""
Session: {msg.session_id}
Group: {msg.group_id}
Thread: {msg.thread_id}
Total interactions: {self.interaction_count}
Last response: {sess.get('last_response', 'none')}
            """.strip()
            return Message(
                id=f"reply-{datetime.now(timezone.utc).timestamp()}",
                session_id=msg.session_id,
                from_instance="handler",
                sender=msg.sender,
                ts=datetime.now(timezone.utc),
                text=dump,
            )
        
        if msg.group_id and not msg.bot_mentioned:
            print("  [IGNORED - Group message without @mention]")
            return None
        
        response_text = f"Echo [{msg.from_instance}]: {msg.text or '(no text)'}"
        
        return Message(
            id=f"reply-{datetime.now(timezone.utc).timestamp()}",
            session_id=msg.session_id,
            from_instance="handler",
            sender=msg.sender,
            ts=datetime.now(timezone.utc),
            text=response_text,
        )


HTML_PAGE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Unigate Web Test</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #1a1a2e; color: #eee; }
        .container { max-width: 800px; margin: 0 auto; }
        h1 { color: #00d4ff; }
        .chat { border: 1px solid #333; border-radius: 8px; height: 400px; overflow-y: auto; padding: 15px; background: #16213e; margin-bottom: 15px; }
        .message { margin: 10px 0; padding: 10px; border-radius: 8px; }
        .incoming { background: #0f3460; margin-right: 50px; }
        .outgoing { background: #533483; margin-left: 50px; text-align: right; }
        .sender { font-weight: bold; color: #00d4ff; font-size: 0.9em; }
        .time { font-size: 0.7em; color: #888; }
        .input-area { display: flex; gap: 10px; }
        input { flex: 1; padding: 12px; border: 1px solid #333; border-radius: 8px; background: #16213e; color: #fff; }
        button { padding: 12px 24px; background: #00d4ff; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; }
        button:hover { background: #00a8cc; }
        .interactive { margin-top: 10px; padding: 15px; background: #1a1a2e; border-radius: 8px; }
        .interactive button { margin: 5px; background: #ff9800; }
        .interactive button:hover { background: #e68900; }
        .status { color: #4caf50; margin-bottom: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Unigate Web Test</h1>
        <div class="status" id="status">Connecting...</div>
        <div class="chat" id="chat"></div>
        <div class="input-area">
            <input type="text" id="message" placeholder="Type a message..." onkeypress="if(event.key==='Enter')sendMessage()">
            <button onclick="sendMessage()">Send</button>
            <button onclick="sendInteractive()" style="background:#ff9800;">Interactive</button>
        </div>
    </div>
    <script>
        const sessionId = localStorage.getItem('unigate_session') || (localStorage.setItem('unigate_session', Math.random().toString(36).substr(2, 9)));
        let lastPoll = 0;
        
        async function sendMessage() {
            const input = document.getElementById('message');
            const text = input.value.trim();
            if (!text) return;
            input.value = '';
            
            await fetch('/send', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text, session_id: sessionId })
            });
            poll();
        }
        
        async function sendInteractive() {
            await fetch('/send', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    text: 'Please choose:',
                    session_id: sessionId,
                    interactive: {
                        type: 'confirm',
                        interaction_id: 'test-' + Date.now(),
                        prompt: 'Do you want to proceed?',
                        options: ['yes', 'no'],
                        timeout_seconds: 60
                    }
                })
            });
            poll();
        }
        
        async function poll() {
            try {
                const res = await fetch('/poll?since=' + lastPoll);
                const data = await res.json();
                lastPoll = data.timestamp;
                
                data.messages.forEach(msg => {
                    addMessage(msg);
                });
                
                document.getElementById('status').textContent = 'Connected | Messages: ' + data.messages.length;
            } catch (e) {
                document.getElementById('status').textContent = 'Error: ' + e.message;
            }
        }
        
        function addMessage(msg) {
            const chat = document.getElementById('chat');
            const div = document.createElement('div');
            div.className = 'message ' + (msg.direction === 'incoming' ? 'incoming' : 'outgoing');
            
            let html = '<div class="sender">' + (msg.sender_name || 'User') + '</div>';
            html += '<div>' + (msg.text || '(interactive)') + '</div>';
            html += '<div class="time">' + new Date(msg.timestamp * 1000).toLocaleTimeString() + '</div>';
            
            if (msg.interactive && msg.interactive.options) {
                html += '<div class="interactive">';
                msg.interactive.options.forEach(opt => {
                    html += '<button onclick="respond(\'' + msg.id + '\',\'' + opt + '\')">' + opt + '</button>';
                });
                html += '</div>';
            }
            
            div.innerHTML = html;
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        }
        
        async function respond(msgId, value) {
            await fetch('/send', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    text: 'Response: ' + value,
                    session_id: sessionId,
                    interactive_response: { interaction_id: msgId, value: value }
                })
            });
            poll();
        }
        
        document.getElementById('status').textContent = 'Connected';
        setInterval(poll, 1000);
        poll();
    </script>
</body>
</html>
"""


async def main() -> None:
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    use_telegram = "--telegram" in sys.argv and telegram_token
    
    stores = InMemoryStores()
    exchange = Exchange(
        inbox=stores,
        outbox=stores,
        sessions=stores,
        dedup=stores,
        interactions=stores,
    )
    
    secure_store = NamespacedSecureStore()
    
    web_channel = WebUIChannel(
        instance_id="web",
        store=secure_store.for_instance("web"),
        kernel=exchange,
        config={},
    )
    exchange.register_instance("web", web_channel)
    
    handler = UnifiedHandler(exchange, web_channel)
    exchange.set_handler(handler.handle)
    
    if use_telegram:
        telegram = TelegramChannel(
            instance_id="telegram",
            store=secure_store.for_instance("telegram"),
            kernel=exchange,
            config={"token": telegram_token, "mode": "polling"},
        )
        exchange.register_instance("telegram", telegram)
        exchange.set_retry_policy("telegram", max_attempts=5)
        await telegram.setup()
        await telegram.start()
        print(f"Telegram bot @{telegram_token[:20]}... connected")
    
    print("\n" + "=" * 50)
    print("Unigate Test Server")
    print("=" * 50)
    print("\nWeb UI: http://localhost:8000/")
    if use_telegram:
        print(f"Telegram: Polling active")
    print("\nCommands:")
    print("  /test - Test message")
    print("  /interactive - Send YES/NO confirm")
    print("  /select - Send multi-choice select")
    print("\nPress Ctrl+C to stop\n")
    
    async def outbox_loop() -> None:
        while True:
            await asyncio.sleep(2)
            await exchange.flush_outbox()
    
    outbox_task = asyncio.create_task(outbox_loop())
    
    try:
        from aiohttp import web
        
        async def handle_root(request: web.Request) -> web.Response:
            return web.Response(text=HTML_PAGE, content_type='text/html')
        
        async def handle_send(request: web.Request) -> web.Response:
            try:
                data = await request.json()
            except:
                data = {}
            
            msg_data = {
                "id": f"web-{datetime.now(timezone.utc).timestamp()}",
                "session_id": data.get("session_id", "default"),
                "from_instance": "web",
                "sender": {"id": "web-user", "name": "Web User"},
                "text": data.get("text"),
                "group_id": data.get("group_id"),
                "bot_mentioned": data.get("bot_mentioned", True),
                "thread_id": data.get("thread_id"),
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            
            if data.get("interactive"):
                msg_data["interactive"] = data["interactive"]
            
            if data.get("interactive_response"):
                msg_data["interactive_response"] = data["interactive_response"]
            
            await exchange.ingest("web", msg_data)
            await asyncio.sleep(0.1)
            await exchange.flush_outbox()
            
            return web.json_response({"ok": True})
        
        async def handle_poll(request: web.Request) -> web.Response:
            from urllib.parse import parse_qs
            query = request.query
            since = float(query.get('since', 0))
            
            new_messages = [m for m in web_channel._pending if m.get("timestamp", 0) > since]
            
            return web.json_response({
                "messages": new_messages,
                "timestamp": datetime.now(timezone.utc).timestamp(),
            })
        
        app = web.Application()
        app.router.add_get("/", handle_root)
        app.router.add_post("/send", handle_send)
        app.router.add_get("/poll", handle_poll)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "localhost", 8000)
        await site.start()
        
        print("Server running on http://localhost:8000/")
        print("Open this URL in your browser to test!\n")
        
        while True:
            await asyncio.sleep(1)
            
    except ImportError:
        print("\n[aiohttp not installed]")
        print("Install with: pip install aiohttp")
    
    except KeyboardInterrupt:
        print("\nStopping...")
        if use_telegram and 'telegram' in dir():
            await telegram.stop()
        outbox_task.cancel()


if __name__ == "__main__":
    print("Starting Unigate test server...")
    asyncio.run(main())
