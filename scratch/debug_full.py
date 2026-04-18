#!/usr/bin/env python
"""Debug the routing issue."""
import os
os.environ['TELEGRAM_BOT_TOKEN'] = '8674434491:AAEor504OZ97402INs9Qzao4hOKcYbEnpzU'

import asyncio
from datetime import datetime, timezone
from unigate.gate import Unigate

async def main():
    gate = Unigate.from_config('test_telegram.yaml')
    exchange = gate._exchange
    
    tel = exchange.instances["telegram"].channel
    await tel.setup()
    print(f"Telegram token: {tel._token[:10]}...")
    
    # Check instance manager
    print(f"\nInstance manager instances: {list(exchange.instance_manager.instances.keys())}")
    
    for name, runtime in exchange.instance_manager.instances.items():
        print(f"  {name}: can_execute={runtime.can_execute()}")
    
    # Ingest
    print("\nIngesting...")
    result = await exchange.ingest("web", {
        "id": "debug-test",
        "session_id": "6472159074",
        "text": "Debug test message",
        "sender": {"id": "test", "name": "Test"}
    })
    print(f"Ingest result: {result}")
    
    # Check outbox
    outbox = await exchange._outbox.list_outbox(limit=10)
    print(f"\nOutbox count: {len(outbox)}")
    for o in outbox:
        print(f"  {o.outbox_id}")
        print(f"    destination: {o.destination}")
        print(f"    message.to: {o.message.to}")
        print(f"    message.text: {o.message.text}")
        
        # Check if instance exists
        runtime = exchange.instance_manager.instances.get(o.destination)
        print(f"    runtime found: {runtime is not None}")
        if runtime:
            print(f"    can_execute: {runtime.can_execute()}")
    
    # Check due records
    now = datetime.now(timezone.utc)
    due = await exchange._outbox.due(now, limit=10)
    print(f"\nDue records: {len(due)}")
    
    # Try manual flush
    print("\nAttempting manual flush...")
    for record in due:
        runtime = exchange.instance_manager.instances.get(record.destination)
        if runtime:
            print(f"  Calling from_message for {record.destination}...")
            try:
                result = await runtime.channel.from_message(record.message)
                print(f"  Result: {result}")
            except Exception as e:
                print(f"  Error: {e}")

asyncio.run(main())
