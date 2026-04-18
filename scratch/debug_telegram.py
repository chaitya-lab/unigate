"""Debug Telegram polling."""
import asyncio
import sys
import os
sys.path.insert(0, r"H:\2026\SelfAi\dev\chaitya\unigate\src")

os.environ["TELEGRAM_BOT_TOKEN"] = "8674434491:AAEor504OZ97402INs9Qzao4hOKcYbEnpzU"

from unigate.gate import Unigate

async def test():
    gate = Unigate.from_config(r"H:\2026\SelfAi\dev\chaitya\unigate\test_telegram.yaml")
    exchange = gate._exchange
    
    # Setup and start Telegram
    tel = exchange.instances["telegram"].channel
    print(f"Setting up Telegram...")
    setup = await tel.setup()
    print(f"Setup result: {setup.status}")
    
    # Test direct API call to get updates
    print(f"Testing Telegram API...")
    result = await tel._api_call("getUpdates", {"offset": 0, "timeout": 5})
    print(f"API result: ok={result.get('ok')}, updates={len(result.get('result', []))}")
    
    if result.get("result"):
        for update in result["result"]:
            msg = update.get("message", {})
            chat = msg.get("chat", {})
            print(f"  Message from {chat.get('username')}: {msg.get('text')}")
            print(f"  Chat ID: {chat.get('id')}")

if __name__ == "__main__":
    asyncio.run(test())
