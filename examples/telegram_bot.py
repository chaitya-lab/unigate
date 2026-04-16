"""Telegram bot example with Unigate."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

from unigate import Exchange, Message, NamespacedSecureStore, TelegramChannel
from unigate.stores import InMemoryStores


async def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Set TELEGRAM_BOT_TOKEN environment variable")
        return

    stores = InMemoryStores()
    exchange = Exchange(
        inbox=stores,
        outbox=stores,
        sessions=stores,
        dedup=stores,
        interactions=stores,
    )
    
    secure_store = NamespacedSecureStore()
    channel = TelegramChannel(
        instance_id="telegram",
        store=secure_store.for_instance("telegram"),
        kernel=exchange,
        config={"token": token, "mode": "polling"},
    )
    
    exchange.register_instance("telegram", channel)
    exchange.set_retry_policy("telegram", max_attempts=5)

    @exchange.set_handler
    async def handle(msg: Message) -> Message | None:
        print(f"\n--- INCOMING ---")
        print(f"  From: {msg.sender.name} ({msg.sender.platform_id})")
        print(f"  Text: {msg.text}")
        print(f"  Session: {msg.session_id}")
        print(f"  Group: {msg.group_id}")
        
        if msg.text:
            response_text = f"Echo: {msg.text}"
        else:
            response_text = "Got your message!"
        
        return Message(
            id=f"reply-{datetime.now(timezone.utc).timestamp()}",
            session_id=msg.session_id,
            from_instance="telegram",
            sender=msg.sender,
            ts=datetime.now(timezone.utc),
            text=response_text,
        )

    await channel.setup()
    print(f"Telegram bot ready!")
    print(f"  Token: {token[:20]}...")
    print(f"  Status: READY")
    print(f"\nWaiting for messages... (Ctrl+C to stop)")

    await channel.start()

    outbox_task = asyncio.create_task(flush_loop(exchange))
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        await channel.stop()
        outbox_task.cancel()


async def flush_loop(exchange: Exchange) -> None:
    while True:
        await asyncio.sleep(2)
        await exchange.flush_outbox()


if __name__ == "__main__":
    asyncio.run(main())
