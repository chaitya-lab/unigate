"""Standalone server script."""
import os
os.environ["TELEGRAM_BOT_TOKEN"] = "8674434491:AAEor504OZ97402INs9Qzao4hOKcYbEnpzU"

import asyncio
import threading
from unigate.gate import Unigate
from unigate.runtime import create_app
import uvicorn

def setup_and_run():
    async def async_setup():
        gate = Unigate.from_config("test_telegram.yaml")
        exchange = gate._exchange
        exchange.start_outbox_flush_loop(1.0)
        
        for i, inst in gate._exchange.instances.items():
            await inst.channel.setup()
            await inst.channel.start()
        
        app = create_app(exchange=exchange, mount_prefix="/unigate", port=8080)
        
        for i, inst in gate._exchange.instances.items():
            if getattr(inst.channel, "name", None) == "webui":
                app.register_webui(i, inst.channel)
        
        print("Server starting on http://0.0.0.0:8080")
        print("Web UI: http://localhost:8080/unigate/web/web")
        uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
    
    asyncio.run(async_setup())

if __name__ == "__main__":
    print("Starting server in thread...")
    t = threading.Thread(target=setup_and_run, daemon=True)
    t.start()
    t.join()

