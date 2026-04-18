#!/usr/bin/env python
"""Unigate server with FastAPI."""
import os
os.environ['TELEGRAM_BOT_TOKEN'] = '8674434491:AAEor504OZ97402INs9Qzao4hOKcYbEnpzU'

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
import uvicorn

from unigate.gate import Unigate
from unigate.runtime import UnigateApp, create_app

# Load config
gate = Unigate.from_config('test_telegram.yaml')
exchange = gate._exchange

# Create ASGI app
app = create_app(exchange=exchange, mount_prefix='/unigate', port=8080)

# Register webui channels
for i, inst in exchange.instances.items():
    if getattr(inst.channel, 'name', None) == 'webui':
        app.register_webui(i, inst.channel)

# Create FastAPI app
fastapi_app = FastAPI(title="Unigate")

@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    await app.start()
    print("Server started!")
    yield
    await app.stop()
    print("Server stopped!")

fastapi_app.router.lifespan_context = lifespan

# Status endpoint
@fastapi_app.get("/unigate/status")
async def status():
    return {"ok": True, "message": "Unigate running"}

# Health endpoint
@fastapi_app.get("/unigate/health")
async def health():
    return {"ok": True}

# Webhook endpoint
@fastapi_app.post("/unigate/webhook/{instance_id}")
async def webhook(instance_id: str, request: Request):
    raw = await request.json()
    status = await exchange.ingest(instance_id, raw)
    return {"status": status}

# Web UI endpoint - serve the HTML
@fastapi_app.get("/unigate/web/{instance_id}")
async def web_ui(instance_id: str, request: Request):
    return HTMLResponse("<html><body>Web UI for " + instance_id + "</body></html>")

@fastapi_app.post("/unigate/web/{instance_id}/send")
async def web_send(instance_id: str, request: Request):
    raw = await request.json()
    status = await exchange.ingest(instance_id, {
        "id": raw.get("id", ""),
        "session_id": raw.get("session_id", ""),
        "sender": {"id": "web", "name": "Web User"},
        "text": raw.get("text", ""),
    })
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8080)