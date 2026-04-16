"""Base class and registry for transport protocols."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from ..message import Message


class TransportProtocol(Protocol):
    """Protocol for message transport extensions."""

    name: str

    async def send(self, msg: Message, config: dict[str, Any]) -> bool:
        """Send message via this transport. Return True on success."""
        ...


class TransportRegistry:
    """Registry for transport protocols."""

    def __init__(self) -> None:
        self._transports: dict[str, type[TransportProtocol]] = {}

    def register(self, cls: type[TransportProtocol]) -> None:
        """Register a transport class."""
        name = getattr(cls, "name", None)
        if name:
            self._transports[name] = cls

    def get(self, name: str) -> type[TransportProtocol] | None:
        """Get a transport class by name."""
        return self._transports.get(name)

    def create(self, name: str) -> TransportProtocol | None:
        """Create a transport instance by name."""
        cls = self.get(name)
        if cls is None:
            return None
        try:
            return cls()
        except Exception:
            return None

    def list_names(self) -> list[str]:
        """List all registered transport names."""
        return list(self._transports.keys())


_global_registry: TransportRegistry | None = None


def get_transport_registry() -> TransportRegistry:
    """Get the global transport registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = TransportRegistry()
        _global_registry.register(HTTPTransport)
        _global_registry.register(FTPTransport)
        _global_registry.register(WebSocketTransport)
    return _global_registry


from .http import HTTPTransport
from .ftp import FTPTransport
from .websocket import WebSocketTransport
