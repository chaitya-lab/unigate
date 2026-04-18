#!/usr/bin/env python
"""Test routing in the running server."""
import asyncio
import os
os.environ['TELEGRAM_BOT_TOKEN'] = '8674434491:AAEor504OZ97402INs9Qzao4hOKcYbEnpzU'

from unigate.gate import Unigate

async def test_routing():
    gate = Unigate.from_config('test_telegram.yaml')
    exchange = gate._exchange
    
    print("Testing routing in isolated context...")
    print(f"Routing enabled: {exchange.is_routing_enabled()}")
    
    # Setup telegram channel first
    telegram_runtime = exchange.instance_manager.instances.get("telegram")
    if telegram_runtime and not telegram_runtime.channel._token:
        print("\nCalling setup() on telegram channel...")
        result = await telegram_runtime.channel.setup()
        print(f"Setup result: {result}")
    
    # Check routing rules
    engine = exchange.get_routing_engine()
    if engine:
        rules = engine.get_rules()
        print(f"Routing rules: {len(rules)}")
    
    # Send a test message to web instance
    print("\nSending test message to 'web' instance...")
    result = await exchange.ingest("web", {
        "id": "test-123",
        "session_id": "test-session-1",
        "sender": {"id": "test-user", "name": "Test User"},
        "text": "Hello from web routing test!",
    })
    print(f"Ingest result: {result}")
    
    # Check outbox
    outbox = await exchange._outbox.list_outbox(limit=10)
    print(f"Outbox count: {len(outbox)}")
    for o in outbox:
        print(f"  -> {o.destination}: {o.message.text}")
    
    # Flush outbox
    print("\nFlushing outbox...")
    flushed = await exchange.flush_all_outbox()
    print(f"Flushed {flushed} messages")
    
    # Check if any messages were sent to telegram
    telegram_channel = telegram_runtime.channel
    if hasattr(telegram_channel, '_sent'):
        print(f"\nTelegram channel sent messages: {len(telegram_channel._sent)}")
        for msg in telegram_channel._sent[-3:]:  # Last 3 messages
            print(f"  -> {msg.text}")

asyncio.run(test_routing())

asyncio.run(test_routing())
