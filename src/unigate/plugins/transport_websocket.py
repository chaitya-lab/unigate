"""WebSocket transport plugin for real-time messaging."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..message import Message


class WebSocketTransport:
    """Send messages via WebSocket."""
    
    name = "websocket"
    type = "transport"
    description = "WebSocket-based real-time message transport"
    
    async def send(self, msg: Message, config: dict[str, Any]) -> bool:
        import asyncio
        import json
        
        url = config.get("url")
        if not url:
            return False
        
        headers = config.get("headers", {})
        timeout = config.get("timeout", 10)
        
        payload = {
            "id": msg.id,
            "text": msg.text,
            "sender": {
                "id": msg.sender.platform_id,
                "name": msg.sender.name,
            },
            "session_id": msg.session_id,
        }
        
        if msg.media:
            payload["media"] = msg.media
        
        try:
            import websockets
            async with websockets.connect(url, extra_headers=headers) as ws:
                await asyncio.wait_for(ws.send(json.dumps(payload)), timeout=timeout)
                return True
        except Exception:
            return False


class WebSocketClient:
    """WebSocket client for receiving and sending messages."""
    
    name = "websocket_client"
    type = "transport"
    description = "Bidirectional WebSocket client"
    
    def __init__(self) -> None:
        self._connected = False
    
    async def connect(self, url: str, headers: dict[str, str] | None = None) -> bool:
        import asyncio
        import websockets
        
        try:
            self._ws = await websockets.connect(url, extra_headers=headers or {})
            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False
    
    async def send(self, msg: Message, config: dict[str, Any]) -> bool:
        import asyncio
        import json
        
        if not getattr(self, "_connected", False):
            url = config.get("url")
            headers = config.get("headers", {})
            if not await self.connect(url, headers):
                return False
        
        payload = {
            "id": msg.id,
            "text": msg.text,
            "sender": {
                "id": msg.sender.platform_id,
                "name": msg.sender.name,
            },
            "session_id": msg.session_id,
        }
        
        try:
            await self._ws.send(json.dumps(payload))
            return True
        except Exception:
            return False
    
    async def receive(self) -> dict[str, Any] | None:
        import json
        
        if not getattr(self, "_connected", False):
            return None
        
        try:
            data = await self._ws.recv()
            return json.loads(data)
        except Exception:
            return None
    
    async def close(self) -> None:
        if getattr(self, "_ws", None):
            await self._ws.close()
            self._connected = False
