"""Unified plugin base classes and registry."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from ..message import Message


class PluginType(Enum):
    """Plugin type enumeration."""
    CHANNEL = "channel"
    MATCH = "match"
    TRANSFORM = "transform"
    TRANSPORT = "transport"


class ChannelPlugin(Protocol):
    """Channel plugin - receives raw input and converts to Message."""
    
    name: str
    type: str = "channel"
    
    async def receive(self, raw: dict[str, Any]) -> Message | None:
        """Convert raw input to Message."""
        ...
    
    async def send(self, msg: Message) -> dict[str, Any] | None:
        """Convert Message to platform format."""
        ...


class MatcherPlugin(Protocol):
    """Matcher plugin - evaluates if message matches condition."""
    
    name: str
    type: str = "match"
    
    def match(self, msg: Message, value: Any) -> bool:
        """Check if message matches. Return True if matched."""
        ...


class TransformPlugin(Protocol):
    """Transform plugin - modifies message content."""
    
    name: str
    type: str = "transform"
    
    async def transform(self, msg: Message, config: dict[str, Any]) -> Message:
        """Transform message. Return modified message."""
        ...


class TransportPlugin(Protocol):
    """Transport plugin - delivers message to external service."""
    
    name: str
    type: str = "transport"
    
    async def send(self, msg: Message, config: dict[str, Any]) -> bool:
        """Send message externally. Return True on success."""
        ...


class PluginRegistry:
    """Unified registry for all plugin types."""
    
    def __init__(self) -> None:
        self.channels: dict[str, type[ChannelPlugin]] = {}
        self.matches: dict[str, type[MatcherPlugin]] = {}
        self.transforms: dict[str, type[TransformPlugin]] = {}
        self.transports: dict[str, type[TransportPlugin]] = {}
    
    def register(self, cls: type) -> None:
        """Register a plugin by its type attribute."""
        plugin_type = getattr(cls, "type", None)
        name = getattr(cls, "name", None)
        
        if not name:
            return
        
        if plugin_type == "channel":
            self.channels[name] = cls
        elif plugin_type == "match":
            self.matches[name] = cls
        elif plugin_type == "transform":
            self.transforms[name] = cls
        elif plugin_type == "transport":
            self.transports[name] = cls
    
    def register_channel(self, cls: type[ChannelPlugin]) -> None:
        name = getattr(cls, "name", None)
        if name:
            self.channels[name] = cls
    
    def register_match(self, cls: type[MatcherPlugin]) -> None:
        name = getattr(cls, "name", None)
        if name:
            self.matches[name] = cls
    
    def register_transform(self, cls: type[TransformPlugin]) -> None:
        name = getattr(cls, "name", None)
        if name:
            self.transforms[name] = cls
    
    def register_transport(self, cls: type[TransportPlugin]) -> None:
        name = getattr(cls, "name", None)
        if name:
            self.transports[name] = cls
    
    def get_channel(self, name: str) -> type[ChannelPlugin] | None:
        return self.channels.get(name)
    
    def get_match(self, name: str) -> type[MatcherPlugin] | None:
        return self.matches.get(name)
    
    def get_transform(self, name: str) -> type[TransformPlugin] | None:
        return self.transforms.get(name)
    
    def get_transport(self, name: str) -> type[TransportPlugin] | None:
        return self.transports.get(name)
    
    def create_match(self, name: str) -> MatcherPlugin | None:
        cls = self.get_match(name)
        if cls:
            try:
                return cls()
            except Exception:
                pass
        return None
    
    def create_transform(self, name: str) -> TransformPlugin | None:
        cls = self.get_transform(name)
        if cls:
            try:
                return cls()
            except Exception:
                pass
        return None
    
    def create_transport(self, name: str) -> TransportPlugin | None:
        cls = self.get_transport(name)
        if cls:
            try:
                return cls()
            except Exception:
                pass
        return None


_global_registry: PluginRegistry | None = None


def get_registry() -> PluginRegistry:
    """Get the global plugin registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = PluginRegistry()
        _load_builtins(_global_registry)
    return _global_registry


def _load_builtins(registry: PluginRegistry) -> None:
    """Load built-in plugins."""
    from .channel_web import WebChannelPlugin
    from .channel_telegram import TelegramChannelPlugin
    from .match_from import FromMatcher
    from .match_text import TextContainsMatcher, TextPatternMatcher
    from .match_sender import SenderMatcher, SenderPatternMatcher
    from .match_media import HasMediaMatcher, HasAttachmentMatcher
    from .match_time import DayOfWeekMatcher, HourOfDayMatcher
    from .transform_truncate import TruncateTransform
    from .transform_extract import ExtractSubjectTransform
    from .transform_add import AddMetadataTransform, AddTimestampTransform
    from .transport_http import HTTPTransport
    
    registry.register(WebChannelPlugin)
    registry.register(TelegramChannelPlugin)
    registry.register(FromMatcher)
    registry.register(TextContainsMatcher)
    registry.register(TextPatternMatcher)
    registry.register(SenderMatcher)
    registry.register(SenderPatternMatcher)
    registry.register(HasMediaMatcher)
    registry.register(HasAttachmentMatcher)
    registry.register(DayOfWeekMatcher)
    registry.register(HourOfDayMatcher)
    registry.register(TruncateTransform)
    registry.register(ExtractSubjectTransform)
    registry.register(AddMetadataTransform)
    registry.register(AddTimestampTransform)
    registry.register(HTTPTransport)


def register_plugin_dirs(directories: list[str]) -> None:
    """Register plugins from directories."""
    registry = get_registry()
    
    for dir_path in directories:
        path = Path(dir_path)
        if not path.exists() or not path.is_dir():
            continue
        
        for file_path in path.iterdir():
            if not file_path.suffix == ".py" or file_path.name.startswith("_"):
                continue
            
            _load_plugin_file(registry, file_path)


def _load_plugin_file(registry: PluginRegistry, file_path: Path) -> None:
    """Load plugins from a single file."""
    module_name = file_path.stem
    
    try:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if not spec or not spec.loader:
            return
        
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type):
                registry.register(attr)
    except Exception:
        pass
