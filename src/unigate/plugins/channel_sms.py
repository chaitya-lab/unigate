"""SMS channel adapter - demonstrates capability degradation."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, ClassVar
from uuid import uuid4

from ..capabilities import ChannelCapabilities
from ..channel import BaseChannel, RawRequest, SendResult
from ..lifecycle import HealthCheckResult, HealthStatus, SetupResult, SetupStatus
from ..message import Interactive, InteractiveResponse, Message, Sender
from ..stores import SecureStore


SMS_MAX_LENGTH = 160


class SMSChannel(BaseChannel):
    """SMS channel with text-only support.
    
    Demonstrates degrading rich interactions to plain text.
    This channel doesn't support any interactive - converts to text.
    """
    
    name: ClassVar[str] = "sms"
    type: ClassVar[str] = "channel"
    transport: ClassVar[str] = "http"
    auth_method: ClassVar[str] = "credentials"
    parameters = {
        "from_number": {"type": "str", "description": "Sender phone number"},
        "provider": {"type": "str", "description": "SMS provider: twilio|awssns", "default": "twilio"},
    }
    
    def __init__(
        self,
        instance_id: str,
        store: SecureStore,
        kernel: Any,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.instance_id = instance_id
        self.store = store
        self.kernel = kernel
        self.config = config or {}
        self._sent: list[Message] = []
    
    async def setup(self) -> SetupResult:
        return SetupResult(status=SetupStatus.READY)
    
    async def start(self) -> None:
        pass
    
    async def stop(self) -> None:
        pass
    
    def to_message(self, raw: dict[str, Any]) -> Message:
        sender_data = raw.get("sender", {})
        sender = Sender(
            platform_id=str(sender_data.get("id", "unknown")),
            name=str(sender_data.get("name", "Sender")),
        )
        
        interactive_response = None
        if raw.get("interactive_response"):
            ir = raw["interactive_response"]
            interactive_response = InteractiveResponse(
                interaction_id=ir.get("interaction_id", ""),
                type=ir.get("type", "text"),
                value=ir.get("value", ""),
                raw=ir,
            )
        
        return Message(
            id=raw.get("id", str(uuid4())),
            session_id=raw.get("session_id", str(uuid4())),
            from_instance=self.instance_id,
            sender=sender,
            ts=datetime.now(timezone.utc),
            text=raw.get("text"),
            interactive_response=interactive_response,
            raw=raw,
            metadata={},
        )
    
    async def from_message(self, msg: Message) -> SendResult:
        self._sent.append(msg)
        
        # Send logic will be here
        # For demo, just track it
        return SendResult(success=True, provider_message_id=f"sms:{msg.id}")
    
    @property
    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(
            direction="bidirectional",
            supports_groups=False,
            supports_threads=False,
            supports_reply_to=False,
            supports_typing_indicator=False,
            supports_media_send=True,
            supported_interaction_types=[],  # No interactive support!
            max_message_length=SMS_MAX_LENGTH,
        )
    
    def _degrade_interactive(self, msg: Message) -> Message:
        """Convert interactive to text message.
        
        Handles several degradation patterns:
        
        1. Confirm: "Continue? (yes/no)"
        2. Select: "Choose: 1. Option A / 2. Option B / 3. Option C"
        3. Text input: "Enter your message and send"
        
        We also store the interaction_id in metadata so when user replies,
        we can look it up and restore the interactive response.
        """
        if not msg.interactive:
            return msg
        
        interaction = msg.interactive
        prompt = interaction.prompt
        
        # Handle different interaction types
        if interaction.type == "confirm":
            options = interaction.options or ["yes", "no"]
            prompt = f"{prompt} ({'/'.join(options)})"
            
        elif interaction.type == "select" or interaction.type == "multi_select":
            if interaction.options:
                # Numbered options: "1. Option A / 2. Option B"
                numbered = [f"{i+1}. {opt}" for i, opt in enumerate(interaction.options)]
                prompt = f"{prompt}: {' / '.join(numbered)}"
            else:
                prompt = f"{prompt} (enter your response)"
                
        elif interaction.type == "text_input":
            prompt = f"{prompt} (reply with text)"
            
        elif interaction.type == "password":
            prompt = f"{prompt} (send password)"
            
        elif interaction.type == "number":
            if interaction.min_value and interaction.max_value:
                prompt = f"{prompt} ({interaction.min_value}-{interaction.max_value})"
            else:
                prompt = f"{prompt} (send number)"
                
        else:
            # Generic fallback
            prompt = f"{prompt} (reply)"
        
        # Truncate if needed
        if len(prompt) > SMS_MAX_LENGTH - 10:
            prompt = prompt[:SMS_MAX_LENGTH - 10] + ".."
        
        return Message(
            id=msg.id,
            session_id=msg.session_id,
            from_instance=msg.from_instance,
            sender=msg.sender,
            ts=msg.ts,
            platform_id=msg.platform_id,
            to=msg.to,
            thread_id=msg.thread_id,
            group_id=msg.group_id,
            receiver_id=msg.receiver_id,
            bot_mentioned=msg.bot_mentioned,
            text=prompt,
            media=msg.media,
            interactive=None,
            actions=msg.actions,
            reply_to_id=msg.reply_to_id,
            reactions=msg.reactions,
            edit_of_id=msg.edit_of_id,
            deleted_id=msg.deleted_id,
            stream_id=msg.stream_id,
            is_final=msg.is_final,
            raw=msg.raw,
            metadata={
                **msg.metadata,
                "_degraded": True,
                "_original_interaction_id": msg.interactive.interaction_id,
            },
        )
    
    def _parse_response(self, msg: Message) -> Message:
        """Parse user text response back to interactive.
        
        When user replies to degraded message, check if this is a response
        and reconstruct the interactive.response.
        """
        if msg.metadata.get("_degraded"):
            orig_id = msg.metadata.get("_original_interaction_id")
            if orig_id and msg.text:
                return Message(
                    id=msg.id,
                    session_id=msg.session_id,
                    from_instance=msg.from_instance,
                    sender=msg.sender,
                    ts=msg.ts,
                    text=msg.text,
                    interactive=Interactive(
                        interaction_id=orig_id,
                        type="confirm",
                        prompt="",
                        response=InteractiveResponse(
                            interaction_id=orig_id,
                            type="confirm",
                            value=msg.text.strip().lower(),
                            raw={},
                        ),
                    ),
                    raw=msg.raw,
                    metadata={},
                )
        return msg
    
    async def reset_setup(self) -> None:
        pass
    
    async def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(
            status=HealthStatus.HEALTHY,
            message="SMS channel ready",
            last_check=datetime.now(timezone.utc),
        )
    
    async def background_tasks(self) -> list[object]:
        return []


__all__ = ["SMSChannel"]