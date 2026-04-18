#!/usr/bin/env python
"""Run the unigate server."""
import os
os.environ['TELEGRAM_BOT_TOKEN'] = '8674434491:AAEor504OZ97402INs9Qzao4hOKcYbEnpzU'

import asyncio
from unigate.gate import Unigate

async def main():
    print("Loading unigate...")
    gate = Unigate.from_config('test_telegram.yaml')
    exchange = gate._exchange
    
    # Setup all channels
    print("\n=== Setup Phase ===")
    for instance_id, inst in exchange.instances.items():
        channel = inst.channel
        if hasattr(channel, 'setup'):
            await channel.setup()
            print(f"Setup {instance_id}: OK")
    
    print("\n=== Start Phase ===")
    for instance_id, inst in exchange.instances.items():
        channel = inst.channel
        if hasattr(channel, 'start'):
            asyncio.create_task(channel.start())
            print(f"Started {instance_id}")
    
    # Test routing
    print("\n=== Test: Web to Telegram ===")
    await exchange.ingest("web", {
        "id": "test-1",
        "session_id": "test-session",
        "sender": {"id": "web", "name": "Web User"},
        "text": "Hello from unigate!",
    })
    
    await asyncio.sleep(1)
    
    outbox = await exchange._outbox.list_outbox(limit=10)
    print(f"Outbox: {len(outbox)} messages")
    for o in outbox:
        print(f"  -> {o.destination}: {o.message.text}")
    
    flushed = await exchange.flush_all_outbox()
    print(f"Flushed: {flushed}")
    
    tg = exchange.instances.get("telegram")
    if tg:
        print(f"Telegram sent: {len(tg.channel._sent)}")

if __name__ == "__main__":
    asyncio.run(main())