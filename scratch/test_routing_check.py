#!/usr/bin/env python
import os
os.environ['TELEGRAM_BOT_TOKEN'] = '8674434491:AAEor504OZ97402INs9Qzao4hOKcYbEnpzU'

import asyncio
from unigate.gate import Unigate

async def main():
    gate = Unigate.from_config('test_telegram.yaml')
    exchange = gate._exchange
    
    print(f"Routing enabled: {exchange.is_routing_enabled()}")
    
    if exchange.is_routing_enabled():
        engine = exchange.get_routing_engine()
        if engine:
            print(f"Rules: {len(engine._rules)}")
            for rule in engine._rules:
                print(f"  - {rule.name}: match={rule.match}, actions={rule.actions.forward_to}")
        else:
            print("No routing engine!")
    else:
        print("Routing NOT enabled!")

asyncio.run(main())
