"""Base adapter and kernel-facing protocols."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Protocol

from .capabilities import ChannelCapabilities
from .events import KernelEvent
from .lifecycle import HealthStatus, SetupResult
from .message import Message


class SecureStore(Protocol):
    """Namespaced credential storage for one instance."""

    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str) -> None: ...
    async def delete(self, key: str) -> None: ...


class KernelHandle(Protocol):
    """Small kernel surface exposed to adapters."""

    async def emit_event(self, event: KernelEvent) -> None: ...


@dataclass(slots=True)
class RawRequest:
    """Generic incoming HTTP request shape for signature verification."""

    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    query: dict[str, str] = field(default_factory=dict)
    path_params: dict[str, str] = field(default_factory=dict)


class BaseChannel(Protocol):
    """The only adapter contract that matters."""

    name: ClassVar[str]
    transport: ClassVar[str]
    auth_method: ClassVar[str]

    instance_id: str
    config: dict[str, Any]
    store: SecureStore
    kernel: KernelHandle

    async def setup(self) -> SetupResult:
        """Authenticate and prepare the instance."""

    async def start(self) -> None:
        """Begin receiving from the transport."""

    async def stop(self) -> None:
        """Disconnect gracefully."""

    def to_message(self, raw: dict[str, Any]) -> Message:
        """Convert transport payload to a universal message."""

    async def from_message(self, msg: Message) -> None:
        """Convert universal message to transport send."""

    @property
    def capabilities(self) -> ChannelCapabilities:
        """Declared adapter capabilities."""

    async def reset_setup(self) -> None:
        """Optional auth reset hook."""

    async def health_check(self) -> HealthStatus:
        """Optional health signal."""

    async def background_tasks(self) -> list[object]:
        """Optional long-running tasks owned by the adapter."""

    async def verify_signature(self, request: RawRequest) -> bool:
        """Optional HTTP verification hook."""
