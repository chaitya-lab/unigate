"""HTTP transport plugin."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..message import Message


class HTTPTransport:
    """Send messages via HTTP/HTTPS."""
    
    name = "http"
    type = "transport"
    
    async def send(self, msg: Message, config: dict[str, Any]) -> bool:
        import httpx
        
        url = config.get("url")
        if not url:
            return False
        
        method = config.get("method", "POST").upper()
        headers = config.get("headers", {})
        timeout = config.get("timeout", 30)
        
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
            async with httpx.AsyncClient(timeout=timeout) as client:
                if method == "GET":
                    response = await client.get(url, headers=headers, params=payload)
                else:
                    response = await client.post(url, headers=headers, json=payload)
                return 200 <= response.status_code < 300
        except Exception:
            return False


class WebhookTransport:
    """Alias for HTTP transport."""
    
    name = "webhook"
    type = "transport"
    
    async def send(self, msg: Message, config: dict[str, Any]) -> bool:
        http = HTTPTransport()
        return await http.send(msg, config)
