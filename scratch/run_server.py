#!/usr/bin/env python
"""Run unigate server - minimal version."""
# Set TELEGRAM_BOT_TOKEN env var before running

import asyncio
import aiohttp
import aiohttp.web
from unigate.gate import Unigate

async def main():
    # Load and setup
    gate = Unigate.from_config('test_telegram.yaml')
    exchange = gate._exchange
    
    for inst in exchange.instances.values():
        await inst.channel.setup()
    
    # Get web channel for UI
    webui_channel = exchange.instances["web"].channel
    
    # Start channels
    for inst in exchange.instances.values():
        asyncio.create_task(inst.channel.start())
    
    # Start outbox flush loop
    async def flush_loop():
        while True:
            await asyncio.sleep(1)
            await exchange.flush_all_outbox()
    asyncio.create_task(flush_loop())
    
    # Handlers
    async def status(request):
        return aiohttp.web.json_response({
            "ok": True,
            "instances": list(exchange.instances.keys())
        })
    
    async def send(request):
        data = await request.json()
        text = data.get("text", "")
        
        # Show what's happening
        print(f"SEND: {text}")
        
        # Store in web channel's pending (for poll)
        web_ch = exchange.instances["web"].channel
        web_ch._pending.append({
            "text": text,
            "sender_name": "You",
            "direction": "outgoing"
        })
        
        # Ingest for routing
        await exchange.ingest("web", {
            "id": data.get("id") or "web-1",
            "session_id": data.get("session_id") or "default",
            "sender": {"id": "web", "name": "Web"},
            "text": text,
        })
        
        # Count outbox
        outbox = await exchange._outbox.list_outbox(limit=10)
        print(f"OUTBOX: {len(outbox)} messages")
        
        # Flush to Telegram
        flushed = await exchange.flush_all_outbox()
        print(f"FLUSHED: {flushed}")
        
        # Check Telegram channel sent
        tg = exchange.instances.get("telegram")
        if tg:
            print(f"TELEGRAM _sent: {len(tg.channel._sent)}")
        
        return aiohttp.web.json_response({
            "ok": True, 
            "outbox": len(outbox), 
            "flushed": flushed
        })
    
    async def poll(request):
        web_ch = exchange.instances["web"].channel
        messages = web_ch._pending[-20:] if hasattr(web_ch, '_pending') else []
        return aiohttp.web.json_response({"messages": messages})
    
    async def inbox(request):
        inbox_messages = await exchange._inbox.list_inbox(limit=20)
        return aiohttp.web.json_response({
            "inbox": [
                {
                    "id": m.message_id,
                    "instance": m.instance_id,
                    "text": m.message.text,
                    "from": m.message.sender.name if m.message.sender else "?"
                }
                for m in inbox_messages
            ]
        })
    
    # Simple WebUI HTML
    WEBUI_HTML = '''<!DOCTYPE html>
<html>
<head>
    <title>Unigate Web</title>
    <style>
        body { font-family: Arial; margin: 20px; background: #1a1a2e; color: #eee; }
        .chat { height: 300px; overflow-y: auto; padding: 10px; background: #16213e; border-radius: 8px; margin-bottom: 10px; }
        .msg { padding: 8px; margin: 5px 0; border-radius: 8px; }
        .in { background: #0f3460; margin-right: 50px; }
        .out { background: #533483; margin-left: 50px; text-align: right; }
        input { padding: 10px; width: 70%; }
        button { padding: 10px 20px; background: #00d4ff; border: none; border-radius: 8px; }
    </style>
</head>
<body>
    <h1>Unigate Web</h1>
    <div class="chat" id="chat"></div>
    <input id="msg" placeholder="Type message...">
    <button onclick="send()">Send</button>
    <script>
    let last = 0;
    async function send() {
        let input = document.getElementById('msg');
        await fetch('/unigate/web/send', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({text: input.value})
        });
        input.value = '';
        poll();
    }
    async function poll() {
        let r = await fetch('/unigate/web/poll?since=' + last);
        let data = await r.json();
        let chat = document.getElementById('chat');
        data.messages.forEach(m => {
            let div = document.createElement('div');
            div.className = 'msg ' + (m.direction === 'outgoing' ? 'out' : 'in');
            div.textContent = (m.sender_name || '?') + ': ' + (m.text || '');
            chat.appendChild(div);
        });
        if (data.messages.length) last = data.timestamp;
    }
    setInterval(poll, 1000);
    poll();
    </script>
</body>
</html>'''

    async def webui(request):
        return aiohttp.web.Response(text=WEBUI_HTML, content_type='text/html')
    
    app = aiohttp.web.Application()
    app.router.add_get('/unigate/status', status)
    app.router.add_get('/unigate/web/web', webui)
    app.router.add_post('/unigate/web/send', send)
    app.router.add_get('/unigate/web/poll', poll)
    app.router.add_get('/unigate/inbox', inbox)
    
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print("=" * 40)
    print("Server running on http://0.0.0.0:8080")
    print("Endpoints: /unigate/status, /unigate/web/send, /unigate/web/poll")
    print("Send message from Web, I'll check Telegram")
    print("=" * 40)
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())