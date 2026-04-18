"""Quick Telegram test."""
from urllib.request import Request, urlopen
import json

token = "8674434491:AAEor504OZ97402INs9Qzao4hOKcYbEnpzU"
url = f"https://api.telegram.org/bot{token}/getUpdates?offset=0&timeout=5"

print(f"Checking updates...")
r = urlopen(Request(url), timeout=10)
data = json.loads(r.read())

print(f"OK: {data.get('ok')}")
print(f"Updates: {len(data.get('result', []))}")

for u in data.get('result', []):
    msg = u.get('message', {})
    chat = msg.get('chat', {})
    print(f"  Chat ID: {chat.get('id')}")
    print(f"  Username: {chat.get('username')}")
    print(f"  Text: {msg.get('text')}")
