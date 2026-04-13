"""Simple browser/web chat style channel."""

from __future__ import annotations

from ..channel import ChannelCapabilities
from .loopback import LoopbackChannel


class WebChannel(LoopbackChannel):
    """Channel representing a browser chat widget or web inbox."""

    channel_type = "web"
    capabilities = ChannelCapabilities(supports_interactive=True)

    async def receive_browser_message(
        self,
        *,
        message_id: str,
        browser_session_id: str,
        visitor_id: str,
        visitor_name: str,
        text: str,
    ) -> None:
        await self.inject_text(
            channel_message_id=message_id,
            channel_session_key=browser_session_id,
            sender_id=visitor_id,
            sender_name=visitor_name,
            text=text,
            raw={"channel": "web", "browser_session_id": browser_session_id},
        )
