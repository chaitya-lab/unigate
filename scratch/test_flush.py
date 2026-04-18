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
    
    # Ingest and flush
    await exchange.ingest("web", {
        "id": "test-flush",
        "session_id": "6472159074",
        "text": "Test flush",
        "sender": {"id": "test", "name": "Test"}
    })
    
    print(f"Outbox before flush: {len(await exchange._outbox.list_outbox(limit=10))}")
    
    flushed = await exchange.flush_all_outbox()
    print(f"Flushed: {flushed}")
    
    print(f"Telegram _sent: {len(tel._sent)}")
    for msg in tel._sent:
        print(f"  - {msg.text}")

asyncio.run(main())
