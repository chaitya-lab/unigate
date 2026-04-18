#!/usr/bin/env python
"""Test Telegram send."""
import os
os.environ["TELEGRAM_BOT_TOKEN"] = "8674434491:AAEor504OZ97402INs9Qzao4hOKcYbEnpzU"

import asyncio
import sys
sys.path.insert(0, "src")

from unigate.gate import Unigate

async def main():
    gate = Unigate.from_config("test_telegram.yaml")
    exchange = gate._exchange
    
    tel = exchange.instances["telegram"].channel
    await tel.setup()
    print(f"Telegram setup done. Token: {tel._token[:10]}...")
    
    # Send directly to your chat
    from unigate.message import Message, Sender
    from datetime import datetime, timezone
    
    msg = Message(
        id="test-1",
        session_id="6472159074",
        from_instance="test",
        sender=Sender(platform_id="test", name="Test"),
        ts=datetime.now(timezone.utc),
        text="Hello from Unigate! This message is from the Web UI.",
    )
    
    result = await tel.from_message(msg)
    print(f"Send result: {result}")

asyncio.run(main())
