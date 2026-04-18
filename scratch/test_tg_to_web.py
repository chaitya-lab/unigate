#!/usr/bin/env python
"""Test Telegram to Web routing."""
import asyncio
import os
os.environ['TELEGRAM_BOT_TOKEN'] = '8674434491:AAEor504OZ97402INs9Qzao4hOKcYbEnpzU'

from unigate.gate import Unigate

async def test():
    gate = Unigate.from_config('test_telegram.yaml')
    exchange = gate._exchange
    
    telegram = exchange.instances['telegram'].channel
    await telegram.setup()
    # Don't start polling - just test routing
    
    web = exchange.instances['web'].channel
    if hasattr(web, 'setup'):
        await web.setup()
    
    print('=== Telegram to Web Routing Test ===')
    
    print('1. Simulating Telegram message...')
    result = await exchange.ingest('telegram', {
        'id': 'tg-test-456',
        'session_id': 'my-session',
        'sender': {'id': '6472159074', 'name': 'Telegram User'},
        'text': 'Hello from Telegram!',
    })
    print(f'   Ingest result: {result}')
    
    outbox = await exchange._outbox.list_outbox(limit=10)
    print(f'2. Outbox has {len(outbox)} message(s)')
    for o in outbox:
        print(f'   -> {o.destination}: {o.message.text}')
    
    print('3. Flushing outbox...')
    flushed = await exchange.flush_all_outbox()
    print(f'   Flushed: {flushed}')
    
    print('4. Web pending:')
    if hasattr(web, '_pending'):
        for m in web._pending:
            txt = m.get('text', 'N/A')
            print(f'   -> {txt}')

asyncio.run(test())
