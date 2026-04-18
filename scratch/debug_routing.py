"""Debug routing test with flush."""
import asyncio
import sys
sys.path.insert(0, r"H:\2026\SelfAi\dev\chaitya\unigate\src")

from unigate.gate import Unigate

async def test():
    gate = Unigate.from_config(r"H:\2026\SelfAi\dev\chaitya\unigate\test_routing.yaml")
    exchange = gate._exchange
    
    # Start outbox flush loop
    exchange.start_outbox_flush_loop(0.5)
    print("Started outbox flush loop")
    
    # Send a test message via web channel
    print("\n--- Sending test message ---")
    test_raw = {
        "id": "test-routing-1",
        "session_id": "test-session-1",
        "text": "Hello routed message!",
        "sender": {"id": "test-user", "name": "Test User"}
    }
    
    # Ingest
    result = await exchange.ingest("web", test_raw)
    print(f"Ingest result: {result}")
    
    # Check outbox before flush
    outbox_before = await exchange._outbox.list_outbox(limit=100)
    print(f"Outbox before flush: {len(outbox_before)}")
    
    # Wait for flush
    await asyncio.sleep(2)
    
    # Check outbox after flush
    outbox_after = await exchange._outbox.list_outbox(limit=100)
    print(f"Outbox after flush: {len(outbox_after)}")
    
    # Check telegram sent messages
    tel_inst = exchange.instances.get("telegram")
    if tel_inst:
        channel = tel_inst.channel
        sent_count = len(getattr(channel, '_sent', []))
        print(f"Telegram sent messages: {sent_count}")
    
    print("\nDone!")

if __name__ == "__main__":
    asyncio.run(test())
