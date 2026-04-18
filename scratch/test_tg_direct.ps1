# Test Telegram polling directly
$env:TELEGRAM_BOT_TOKEN = "8674434491:AAEor504OZ97402INs9Qzao4hOKcYbEnpzU"

# Just get status - don't start server, just check telegram directly
python -c "
import os
os.environ['TELEGRAM_BOT_TOKEN'] = '8674434491:AAEor504OZ97402INs9Qzao4hOKcYbEnpzU'

import asyncio
from unigate.gate import Unigate

async def test():
    gate = Unigate.from_config('local.yaml')
    exchange = gate._exchange
    
    # Setup telegram
    telegram = exchange.instances['telegram'].channel
    await telegram.setup()
    
    # Check offset
    print(f'Telegram bot offset: {telegram._offset}')
    
    # Manually get updates 
    updates = await telegram._get_updates()
    print(f'Updates available: {len(updates)}')
    for u in updates[:3]:
        msg = u.get('message', {})
        print(f'  - {msg.get("from", {}).get("first_name", "?")}: {msg.get("text", "")}')
    
    # Also try getMe to check bot
    me = await telegram._api_call('getMe', None)
    print(f'Bot info: {me}')

asyncio.run(test())
"