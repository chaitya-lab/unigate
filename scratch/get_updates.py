"""Get pending Telegram updates."""
from urllib.request import Request, urlopen
import json

token = "8674434491:AAEor504OZ97402INs9Qzao4hOKcYbEnpzU"
url = f"https://api.telegram.org/bot{token}/getUpdates?timeout=30"

print("Getting updates...")
r = urlopen(Request(url), timeout=35)
data = json.loads(r.read())

print(f"Received {len(data.get('result', []))} updates")
for u in data.get('result', []):
    msg = u.get('message', {})
    chat = msg.get('chat', {})
    print(f"Chat ID: {chat.get('id')}")
    print(f"Username: {chat.get('username')}")
    print(f"Message: {msg.get('text')}")
    print()
