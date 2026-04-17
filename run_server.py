#!/usr/bin/env python
"""Run unigate server - minimal version."""
import os
os.environ['TELEGRAM_BOT_TOKEN'] = '8674434491:AAEor504OZ97402INs9Qzao4hOKcYbEnpzU'

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
    
    # Start channels
    for inst in exchange.instances.values():
        asyncio.create_task(inst.channel.start())
    
    # Handlers
    async def status(request):
        return aiohttp.web.json_response({
            "ok": True,
            "instances": list(exchange.instances.keys())
        })
    
    async def send(request):
        data = await request.json()
        text = data.get("text", "")
        await exchange.ingest("web", {
            "id": data.get("id") or "web-1",
            "session_id": data.get("session_id") or "default",
            "sender": {"id": "web", "name": "Web"},
            "text": text,
        })
        return aiohttp.web.json_response({"ok": True})
    
    async def poll(request):
        web_ch = exchange.instances["web"].channel
        messages = web_ch._pending[-20:] if hasattr(web_ch, '_pending') else []
        return aiohttp.web.json_response({"messages": messages})
    
    app = aiohttp.web.Application()
    app.router.add_get('/unigate/status', status)
    app.router.add_post('/unigate/web/send', send)
    app.router.add_get('/unigate/web/poll', poll)
    
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print("Server running on http://0.0.0.0:8080")
    print("Endpoints: /unigate/status, /unigate/web/send, /unigate/web/poll")
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())