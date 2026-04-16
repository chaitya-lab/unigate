"""Built-in adapters for local testing and embedding."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from .capabilities import ChannelCapabilities
from .channel import SendResult
from .lifecycle import HealthStatus, SetupResult, SetupStatus
from .message import Message, Sender
from .stores import SecureStore


class InternalAdapter:
    name = "internal"
    transport = "internal"
    auth_method = "none"

    def __init__(self, instance_id: str, store: SecureStore, kernel: Any, config: dict[str, Any] | None = None) -> None:
        self.instance_id = instance_id
        self.store = store
        self.kernel = kernel
        self.config = config or {}
        self.sent: list[Message] = []
        self.fail_next_send: bool = False

    async def setup(self) -> SetupResult:
        return SetupResult(status=SetupStatus.READY)

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    def to_message(self, raw: dict[str, Any]) -> Message:
        # Parse interactive response if present
        interactive = None
        if raw.get("interactive_response"):
            from .message import Interactive, InteractiveResponse
            ir = raw["interactive_response"]
            interactive = Interactive(
                interaction_id=ir.get("interaction_id", str(uuid4())),
                type=ir.get("type", "confirm"),
                prompt="",
                response=InteractiveResponse(
                    interaction_id=ir.get("interaction_id", ""),
                    type=ir.get("type", "confirm"),
                    value=ir.get("value"),
                    raw=ir,
                ) if ir else None,
            )
        
        # Instance-scoped session: use explicit session_id or derive from instance:sender
        explicit_session = raw.get("session_id")
        if explicit_session:
            session_id = explicit_session
        else:
            sender_id = str(raw.get("sender_id", "user-1"))
            session_id = f"{self.instance_id}:{sender_id}"
        
        return Message(
            id=str(raw.get("id", "msg")),
            session_id=session_id,
            from_instance=self.instance_id,
            sender=Sender(platform_id=str(raw.get("sender_id", "user-1")), name=str(raw.get("sender_name", "User"))),
            ts=raw.get("ts", datetime.now(UTC)),
            to=list(raw.get("to", [])),
            text=raw.get("text"),
            bot_mentioned=bool(raw.get("bot_mentioned", True)),
            interactive=interactive,
            raw=raw,
        )

    async def from_message(self, msg: Message) -> SendResult:
        if self.fail_next_send:
            self.fail_next_send = False
            return SendResult(success=False, error="simulated failure")
        self.sent.append(msg)
        return SendResult(success=True, provider_message_id=f"sent:{msg.id}")

    @property
    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(direction="bidirectional", supports_groups=True)

    async def reset_setup(self) -> None:
        return None

    async def health_check(self) -> HealthStatus:
        return HealthStatus.HEALTHY

    async def background_tasks(self) -> list[object]:
        return []

    async def verify_signature(self, request: Any) -> bool:
        return True


class FakeWebhookAdapter(InternalAdapter):
    name = "fake_webhook"
    transport = "http"
