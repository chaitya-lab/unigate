#!/usr/bin/env python
import os
os.environ['TELEGRAM_BOT_TOKEN'] = '8674434491:AAEor504OZ97402INs9Qzao4hOKcYbEnpzU'

import asyncio
from unigate.gate import Unigate

async def main():
    gate = Unigate.from_config('test_telegram.yaml')
    exchange = gate._exchange
    
    tel = exchange.instances["telegram"].channel
    await tel.setup()
    
    print("Before ingest:")
    outbox = await exchange._outbox.list_outbox(limit=10)
    print(f"  Outbox: {len(outbox)}")
    
    print("\nIngesting...")
    result = await exchange.ingest("web", {
        "id": "trace-test",
        "session_id": "6472159074",
        "text": "Trace test",
        "sender": {"id": "test", "name": "Test"}
    })
    print(f"Ingest result: {result}")
    
    print("\nAfter ingest:")
    outbox = await exchange._outbox.list_outbox(limit=10)
    print(f"  Outbox: {len(outbox)}")
    for o in outbox:
        print(f"    -> {o.destination}: {o.message.text}")
    
    print("\nFlushing...")
    flushed = await exchange.flush_all_outbox()
    print(f"Flushed: {flushed}")
    
    print(f"\nTelegram sent: {len(tel._sent)}")

asyncio.run(main())
