"""Test server combining Web UI and Telegram channels."""

from __future__ import annotations

import asyncio
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

Group testing:
Use "Group" button to test group mode
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
    print(f"\nWeb UI: http://localhost:8000/")
    if use_telegram:
        print(f"Telegram: Polling active for @{telegram_token[:20]}...")
    print("\nCommands:")
    print("  /test - Test message")
    print("  /interactive - Send YES/NO confirm")
    print("  /select - Send multi-choice select")
    print("  /dump - Show session info")
    print("  /help - Show help")
    print("\nPress Ctrl+C to stop\n")
    
    async def outbox_loop() -> None:
        while True:
            await asyncio.sleep(2)
            await exchange.flush_outbox()
    
    outbox_task = asyncio.create_task(outbox_loop())
    
    try:
        import aiohttp
        from aiohttp import web as aiohttp_web
        
        async def handle_request(request: aiohttp_web.Request) -> aiohttp_web.Response:
            instance_id = request.match_info.get("instance", "web")
            
            if instance_id == "web":
                await web_channel.handle_web(request.scope, request.receive, request._payload_writer._send)
            
            return aiohttp_web.Response(text="Not found", status=404)
        
        app = aiohttp_web.Application()
        app.router.add_route("{instance}/{{path:.*}}", handle_request)
        app.router.add_route("/", handle_request)
        
        runner = aiohttp_web.AppRunner(app)
        await runner.setup()
        site = aiohttp_web.TCPSite(runner, "localhost", 8000)
        await site.start()
        
        print("Server running on http://localhost:8000/")
        
        while True:
            await asyncio.sleep(1)
            
    except ImportError:
        print("\n[aiohttp not installed]")
        print("Install with: pip install aiohttp")
        print("Or run the bot only with: python -m unigate.channels.telegram")
    
    except KeyboardInterrupt:
        print("\nStopping...")
        if use_telegram and 'telegram' in dir():
            await telegram.stop()
        outbox_task.cancel()


if __name__ == "__main__":
    print("Starting Unigate test server...")
    asyncio.run(main())
