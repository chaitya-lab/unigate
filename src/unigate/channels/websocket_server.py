"""Simple websocket-style channel."""

from __future__ import annotations

from ..channel import ChannelCapabilities
from .loopback import LoopbackChannel


class WebSocketServerChannel(LoopbackChannel):
    """Channel representing persistent websocket clients."""

    channel_type = "websocket_server"
    capabilities = ChannelCapabilities(supports_streaming=True)

    async def receive_frame(
        self,
        *,
        frame_id: str,
        connection_id: str,
        sender_id: str,
        sender_name: str,
        text: str,
    ):
        return await self.inject_text(
            channel_message_id=frame_id,
            channel_session_key=connection_id,
            sender_id=sender_id,
            sender_name=sender_name,
            text=text,
            raw={"channel": "websocket_server", "connection_id": connection_id},
        )
