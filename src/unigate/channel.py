"""Core channel adapter contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

from .envelope import OutboundMessage, UniversalMessage


class HealthStatus(str, Enum):
    """Adapter health check outcomes."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class SetupStatus(str, Enum):
    """Interactive setup phase outcomes."""

    COMPLETE = "complete"
    REQUIRED = "required"
    PENDING = "pending"
    FAILED = "failed"


@dataclass(slots=True)
class SetupResult:
    """Result returned by adapter setup routines."""

    status: SetupStatus
    interaction_type: str | None = None
    interaction_data: dict[str, Any] = field(default_factory=dict)
    message: str | None = None


@dataclass(slots=True)
class ChannelCapabilities:
    """Declared transport capabilities used by the kernel for safe behavior."""

    supports_threads: bool = False
    supports_groups: bool = False
    supports_reactions: bool = False
    supports_message_edit: bool = False
    supports_message_delete: bool = False
    supports_typing_indicator: bool = False
    supports_interactive: bool = False
    supports_streaming: bool = False
    supports_webhooks: bool = False
    supports_polling: bool = False
    max_message_length: int | None = None
    max_media_items: int | None = None


class BaseChannel(Protocol):
    """Protocol every channel adapter must satisfy."""

    contract_version: str
    channel_type: str
    capabilities: ChannelCapabilities

    async def start(self) -> None:
        """Start the adapter runtime."""

    async def stop(self) -> None:
        """Stop the adapter runtime."""

    async def send(self, message: OutboundMessage) -> str:
        """Deliver one outbound message and return the channel message id."""

    async def acknowledge(self, message: UniversalMessage) -> None:
        """Acknowledge receipt to the upstream transport when applicable."""

    async def health_check(self) -> HealthStatus:
        """Report runtime health for lifecycle management."""

    async def setup(self) -> SetupResult:
        """Run or continue interactive setup for auth-bound transports."""
