"""Fake channel for end-to-end tests."""

from __future__ import annotations

from ..channels.loopback import LoopbackChannel


class FakeChannel(LoopbackChannel):
    """Internal-like channel with helpers for injecting inbound traffic."""

    channel_type = "fake"

    async def receive_text(
        self,
        *,
        channel_message_id: str,
        channel_session_key: str,
        sender_id: str,
        sender_name: str,
        text: str,
    ):
        if self.gate is None or self.instance_id is None:
            raise RuntimeError("FakeChannel must be registered before use.")

        return await self.gate.receive_text(
            instance_id=self.instance_id,
            channel_message_id=channel_message_id,
            channel_session_key=channel_session_key,
            sender_id=sender_id,
            sender_name=sender_name,
            text=text,
            raw={"channel": "fake"},
        )
