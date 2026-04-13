"""Simple API-style channel."""

from __future__ import annotations

from .loopback import LoopbackChannel


class ApiChannel(LoopbackChannel):
    """Channel for request/response style application APIs."""

    channel_type = "api"

    async def receive_request(
        self,
        *,
        request_id: str,
        client_id: str,
        sender_name: str,
        text: str,
        conversation_id: str,
    ) -> None:
        await self.inject_text(
            channel_message_id=request_id,
            channel_session_key=conversation_id,
            sender_id=client_id,
            sender_name=sender_name,
            text=text,
            raw={"channel": "api", "conversation_id": conversation_id, "request_id": request_id},
        )
