import os
os.environ['TELEGRAM_BOT_TOKEN'] = '8674434491:AAEor504OZ97402INs9Qzao4hOKcYbEnpzU'

import asyncio
from unigate.gate import Unigate

async def test():
    gate = Unigate.from_config('local.yaml')
    exchange = gate._exchange
    
    telegram = exchange.instances['telegram'].channel
    await telegram.setup()
    
    print('Offset:', telegram._offset)
    updates = await telegram._get_updates()
    print('Updates:', len(updates))
    
    for u in updates[:5]:
        msg = u.get('message', {})
        if msg:
            text = msg.get('text', '')
            name = msg.get('from', {}).get('first_name', '?')
            print(f'  {name}: {text[:30] if text else "(no text)"}')

asyncio.run(test())