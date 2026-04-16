"""Base class and registry for transform extensions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from ..message import Message


class TransformExtension(Protocol):
    """Protocol for message transform extensions."""

    name: str

    async def transform(self, msg: Message, config: dict[str, Any]) -> Message:
        """Transform message content. Return modified message."""
        ...


class TransformRegistry:
    """Registry for transform extensions."""

    def __init__(self) -> None:
        self._transforms: dict[str, type[TransformExtension]] = {}

    def register(self, cls: type[TransformExtension]) -> None:
        """Register a transform class."""
        name = getattr(cls, "name", None)
        if name:
            self._transforms[name] = cls

    def get(self, name: str) -> type[TransformExtension] | None:
        """Get a transform class by name."""
        return self._transforms.get(name)

    def create(self, name: str, config: dict[str, Any] | None = None) -> TransformExtension | None:
        """Create a transform instance by name."""
        cls = self.get(name)
        if cls is None:
            return None
        try:
            return cls()
        except Exception:
            return None

    def list_names(self) -> list[str]:
        """List all registered transform names."""
        return list(self._transforms.keys())


_global_registry: TransformRegistry | None = None


def get_transform_registry() -> TransformRegistry:
    """Get the global transform registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = TransformRegistry()
        _global_registry.register(TruncateTransform)
        _global_registry.register(ExtractSubjectTransform)
        _global_registry.register(AddMetadataTransform)
    return _global_registry


from .truncate import TruncateTransform
from .extract_subject import ExtractSubjectTransform
from .add_metadata import AddMetadataTransform
