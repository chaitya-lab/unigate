#!/usr/bin/env python
"""Unigate Server - Web + Telegram"""
import os
os.environ["TELEGRAM_BOT_TOKEN"] = "8674434491:AAEor504OZ97402INs9Qzao4hOKcYbEnpzU"

import asyncio
import sys
sys.path.insert(0, "src")

from unigate.gate import Unigate
from unigate.runtime import create_app
import uvicorn

async def main():
    print("Loading config...")
    gate = Unigate.from_config("test_telegram.yaml")
    exchange = gate._exchange
    
    print(f"Instances: {list(exchange.instances.keys())}")
    
    exchange.start_outbox_flush_loop(1.0)
    
    for instance_id, inst in exchange.instances.items():
        channel = inst.channel
        if hasattr(channel, "setup"):
            await channel.setup()
        if hasattr(channel, "start"):
            await channel.start()
    
    app = create_app(exchange=exchange, mount_prefix="/unigate", port=8080)
    
    for instance_id, inst in exchange.instances.items():
        channel = inst.channel
        if getattr(channel, "name", None) == "webui":
            app.register_webui(instance_id, channel)
    
    print("")
    print("=" * 50)
    print("UNIGATE SERVER RUNNING")
    print("=" * 50)
    print("Web UI:     http://localhost:8080/unigate/web/web")
    print("Status:     http://localhost:8080/unigate/status")
    print("Telegram:   @unigatetest_bot")
    print("")
    print("TESTING:")
    print("1. Open Web UI in browser")
    print("2. Send message from Web UI -> appears in Telegram")
    print("3. Send message from Telegram -> appears in Web UI")
    print("=" * 50)
    print("")
    
    config = uvicorn.Config(app, host="0.0.0.0", port=8080, log_level="info", lifespan="off")
    await uvicorn.Server(config).serve()

asyncio.run(main())
