"""Quick test to verify Telegram bot token works."""

import asyncio
import os
import json
from urllib.request import Request, urlopen


async def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or "8674434491:AAFbeAdi8RrSSHwSW2gd8XBru1VPAT9evKQ"
    
    print(f"Testing bot token: {token[:20]}...")
    
    url = f"https://api.telegram.org/bot{token}/getMe"
    
    try:
        req = Request(url)
        with urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            
            if data.get("ok"):
                result = data["result"]
                print(f"\n[OK] Bot is valid!")
                print(f"  Name: {result.get('first_name')} {result.get('last_name', '')}")
                print(f"  Username: @{result.get('username')}")
                print(f"  Bot ID: {result.get('id')}")
            else:
                print(f"\n[ERROR] {data.get('description')}")
                return
        
        url2 = f"https://api.telegram.org/bot{token}/getUpdates"
        req2 = Request(url2 + "?limit=1&timeout=0")
        with urlopen(req2, timeout=10) as response:
            data2 = json.loads(response.read().decode())
            if data2.get("ok"):
                updates = data2.get("result", [])
                print(f"\n[INFO] Updates check: {len(updates)} pending updates")
    
    except Exception as exc:
        print(f"\n[ERROR] Connection failed: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
