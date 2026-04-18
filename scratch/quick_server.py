"""Simple test to start server with Web + Telegram."""
import asyncio
import sys
import os
sys.path.insert(0, r"H:\2026\SelfAi\dev\chaitya\unigate\src")

from unigate.gate import Unigate
from unigate.runtime import create_app
import uvicorn

async def test():
    print("Loading config...")
    config_file = r"H:\2026\SelfAi\dev\chaitya\unigate\test_telegram.yaml"
    
    gate = Unigate.from_config(config_file)
    exchange = gate._exchange
    
    print(f"Instances: {list(exchange.instances.keys())}")
    
    # Start background tasks
    exchange.start_outbox_flush_loop(1.0)
    
    # Setup and start all channels
    for instance_id, inst in exchange.instances.items():
        channel = inst.channel if hasattr(inst, "channel") else inst
        print(f"Setting up {instance_id}...")
        try:
            if hasattr(channel, "setup"):
                setup_result = await channel.setup()
                print(f"  setup: {setup_result.status}")
            if hasattr(channel, "start"):
                await channel.start()
                print(f"  started")
        except Exception as e:
            print(f"  error: {e}")
    
    app = create_app(exchange=exchange, mount_prefix="/unigate", port=8080)
    
    for instance_id, inst in exchange.instances.items():
        channel = inst.channel if hasattr(inst, "channel") else inst
        name = getattr(channel, "name", None)
        if name == "webui":
            app.register_webui(instance_id, channel)
    
    print(f"\n========================================")
    print(f"Unigate Server Running!")
    print(f"========================================")
    print(f"Web UI: http://localhost:8080/unigate/web/web")
    print(f"Status: http://localhost:8080/unigate/status")
    print(f"Telegram: @unigatetest_bot")
    print(f"========================================\n")
    
    config = uvicorn.Config(app, host="0.0.0.0", port=8080, log_level="info", lifespan="off")
    server = uvicorn.Server(config)
    await server.serve()

asyncio.run(test())
