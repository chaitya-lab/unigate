#!/usr/bin/env python
"""Run the unigate server."""
import os
os.environ['TELEGRAM_BOT_TOKEN'] = '8674434491:AAEor504OZ97402INs9Qzao4hOKcYbEnpzU'

import asyncio
from contextlib import asynccontextmanager
from unigate.gate import Unigate
from unigate.runtime import create_app

gate = Unigate.from_config('test_telegram.yaml')
exchange = gate._exchange

app = create_app(exchange=exchange, mount_prefix='/unigate', port=8080)

# Register webui
for i, inst in exchange.instances.items():
    if getattr(inst.channel, 'name', None) == 'webui':
        app.register_webui(i, inst.channel)
        print(f"Registered webui: {i}")

@asynccontextmanager
async def lifespan_wrapper(app):
    await app.start()
    print("All channels started!")
    yield
    await app.stop()
    print("Server shutting down!")

# Override app's lifespan
app.lifespan_context = lifespan_wrapper

if __name__ == "__main__":
    import uvicorn
    print("Starting server on http://0.0.0.0:8080...")
    uvicorn.run(app, host="0.0.0.0", port=8080, lifespan="on")
