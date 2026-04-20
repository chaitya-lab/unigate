"""Unified plugin base classes and registry."""

from __future__ import annotations

import importlib
import importlib.util
import sys
import warnings
from dataclasses import dataclass, field
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


@dataclass
class PluginEntry:
    """Entry for a registered plugin."""
    cls: type
    source: str
    enabled: bool = True
    description: str = ""


@dataclass
class PluginParameter:
    """Parameter schema for a plugin."""
    name: str
    type: str
    description: str = ""
    required: bool = False
    default: Any = None


@dataclass
class PluginStatus:
    """Status information for a plugin."""
    name: str
    full_name: str
    type: str
    source: str
    enabled: bool
    available: bool = True
    parameters: list[PluginParameter] = field(default_factory=list)


class ChannelPlugin(Protocol):
    """Channel plugin - receives raw input and converts to Message."""
    
    name: str
    type: str = "channel"
    description: str = ""
    
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
    description: str = ""
    
    def match(self, msg: Message, value: Any) -> bool:
        """Check if message matches. Return True if matched."""
        ...


class TransformPlugin(Protocol):
    """Transform plugin - modifies message content."""
    
    name: str
    type: str = "transform"
    description: str = ""
    
    async def transform(self, msg: Message, config: dict[str, Any]) -> Message:
        """Transform message. Return modified message."""
        ...


class TransportPlugin(Protocol):
    """Transport plugin - delivers message to external service."""
    
    name: str
    type: str = "transport"
    description: str = ""
    
    async def send(self, msg: Message, config: dict[str, Any]) -> bool:
        """Send message externally. Return True on success."""
        ...


class PluginRegistry:
    """Unified registry for all plugin types with management features."""
    
    def __init__(self) -> None:
        self.channels: dict[str, PluginEntry] = {}
        self.matches: dict[str, PluginEntry] = {}
        self.transforms: dict[str, PluginEntry] = {}
        self.transports: dict[str, PluginEntry] = {}
        
        self._warnings: list[str] = []
    
    def _get_full_name(self, name: str, plugin_type: str) -> str:
        """Get type-prefixed name."""
        if "." in name:
            return name
        return f"{plugin_type}.{name}"
    
    def register(self, cls: type, source: str = "builtin") -> None:
        """Register a plugin by its type attribute."""
        plugin_type = getattr(cls, "type", None)
        name = getattr(cls, "name", None)
        description = getattr(cls, "description", "")
        
        if not name:
            return
        
        if plugin_type == "channel":
            self._register_to_dict(self.channels, name, plugin_type, cls, source, description)
        elif plugin_type == "match":
            self._register_to_dict(self.matches, name, plugin_type, cls, source, description)
        elif plugin_type == "transform":
            self._register_to_dict(self.transforms, name, plugin_type, cls, source, description)
        elif plugin_type == "transport":
            self._register_to_dict(self.transports, name, plugin_type, cls, source, description)
    
    def _register_to_dict(
        self, 
        registry: dict[str, PluginEntry],
        name: str,
        plugin_type: str,
        cls: type,
        source: str,
        description: str
    ) -> None:
        """Register plugin to dict with conflict detection."""
        full_name = self._get_full_name(name, plugin_type)
        
        if full_name in registry:
            existing = registry[full_name]
            if source == "user" or source == "plugin_dir":
                if existing.source in ("builtin", "plugin_dir"):
                    self._warnings.append(
                        f"Plugin '{full_name}' from '{source}' overrides '{existing.source}' version"
                    )
                    registry[full_name] = PluginEntry(cls, source, True, description)
            else:
                self._warnings.append(
                    f"Duplicate plugin '{full_name}' (already registered from '{existing.source}')"
                )
        else:
            registry[full_name] = PluginEntry(cls, source, True, description)
    
    def enable(self, name: str) -> bool:
        """Enable a plugin by name."""
        full_name = self._resolve_name(name)
        if not full_name:
            return False
        
        for registry in [self.channels, self.matches, self.transforms, self.transports]:
            if full_name in registry:
                registry[full_name].enabled = True
                return True
        return False
    
    def disable(self, name: str) -> bool:
        """Disable a plugin by name."""
        full_name = self._resolve_name(name)
        if not full_name:
            return False
        
        for registry in [self.channels, self.matches, self.transforms, self.transports]:
            if full_name in registry:
                registry[full_name].enabled = False
                return True
        return False
    
    def _resolve_name(self, name: str) -> str | None:
        """Resolve short name to full name."""
        if "." in name:
            return name
        
        for prefix, registry in [
            ("channel", self.channels),
            ("match", self.matches),
            ("transform", self.transforms),
            ("transport", self.transports),
        ]:
            full_name = f"{prefix}.{name}"
            if full_name in registry:
                return full_name
            if name in registry:
                return name
        
        return name
    
    def get_channel(self, name: str) -> type[ChannelPlugin] | None:
        entry = self._get_entry(self.channels, name)
        return entry.cls if entry and entry.enabled else None
    
    def get_match(self, name: str) -> type[MatcherPlugin] | None:
        entry = self._get_entry(self.matches, name)
        return entry.cls if entry and entry.enabled else None
    
    def get_transform(self, name: str) -> type[TransformPlugin] | None:
        entry = self._get_entry(self.transforms, name)
        return entry.cls if entry and entry.enabled else None
    
    def get_transport(self, name: str) -> type[TransportPlugin] | None:
        entry = self._get_entry(self.transports, name)
        return entry.cls if entry and entry.enabled else None
    
    def _get_entry(self, registry: dict[str, PluginEntry], name: str) -> PluginEntry | None:
        """Get entry by name or full name."""
        full_name = self._resolve_name(name)
        if full_name:
            return registry.get(full_name)
        
        for key, entry in registry.items():
            if key.endswith(f".{name}") or key == name:
                return entry
        return None
    
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
    
    def _get_parameters(self, cls: type) -> list[PluginParameter]:
        """Extract parameters from a plugin class."""
        params = []
        if not cls:
            return params
        param_dict = getattr(cls, "parameters", None)
        if param_dict and isinstance(param_dict, dict):
            for name, info in param_dict.items():
                if isinstance(info, dict):
                    params.append(PluginParameter(
                        name=name,
                        type=info.get("type", "any"),
                        description=info.get("description", ""),
                        required=info.get("required", False),
                        default=info.get("default"),
                    ))
        return params

    def list_plugins(self) -> list[PluginStatus]:
        """List all plugins with status."""
        status = []
        
        for name, entry in self.channels.items():
            status.append(PluginStatus(
                name=entry.cls.name,
                full_name=name,
                type="channel",
                source=entry.source,
                enabled=entry.enabled,
                parameters=self._get_parameters(entry.cls),
            ))
        
        for name, entry in self.matches.items():
            status.append(PluginStatus(
                name=entry.cls.name,
                full_name=name,
                type="match",
                source=entry.source,
                enabled=entry.enabled,
                parameters=self._get_parameters(entry.cls),
            ))
        
        for name, entry in self.transforms.items():
            status.append(PluginStatus(
                name=entry.cls.name,
                full_name=name,
                type="transform",
                source=entry.source,
                enabled=entry.enabled,
                parameters=self._get_parameters(entry.cls),
            ))
        
        for name, entry in self.transports.items():
            status.append(PluginStatus(
                name=entry.cls.name,
                full_name=name,
                type="transport",
                source=entry.source,
                enabled=entry.enabled,
                parameters=self._get_parameters(entry.cls),
            ))
        
        return status
    
    def validate_plugins(self, names: list[str]) -> tuple[list[str], list[str]]:
        """Validate that plugins exist. Returns (valid, missing)."""
        valid = []
        missing = []
        
        for name in names:
            if self.get_match(name) or self.get_transform(name) or self.get_transport(name):
                valid.append(name)
            else:
                missing.append(name)
        
        return valid, missing
    
    def get_warnings(self) -> list[str]:
        """Get registration warnings."""
        return self._warnings.copy()
    
    def clear_warnings(self) -> None:
        """Clear warnings."""
        self._warnings.clear()
    
    def generate_config(self) -> dict[str, Any]:
        """Generate config template from available plugins."""
        enabled = []
        
        for name in sorted(self.channels.keys()):
            if self.channels[name].enabled:
                enabled.append(name)
        
        for name in sorted(self.matches.keys()):
            if self.matches[name].enabled:
                enabled.append(name)
        
        for name in sorted(self.transforms.keys()):
            if self.transforms[name].enabled:
                enabled.append(name)
        
        for name in sorted(self.transports.keys()):
            if self.transports[name].enabled:
                enabled.append(name)
        
        return {
            "plugins": {
                "enabled": enabled,
                "disabled": [],
            }
        }


_global_registry: PluginRegistry | None = None


def get_registry() -> PluginRegistry:
    """Get the global plugin registry.
    
    Plugins are loaded when register_plugin_dirs() is called with config.
    By default, registry is empty until plugin_dirs are configured.
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = PluginRegistry()
    return _global_registry


def _load_builtins(registry: PluginRegistry) -> None:
    """Load built-in plugins from config plugin_dirs.
    
    All plugins now come from plugin_dirs in config, not hardcoded.
    To use built-ins, add to config:
    
    unigate:
      plugin_dirs:
        - ./src/unigate/plugins
    """
    pass  # No hardcoded plugins - all from plugin_dirs


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


def _load_plugin_file(registry: PluginRegistry, file_path: Path | str) -> None:
    """Load plugins from a single file."""
    if isinstance(file_path, str):
        file_path = Path(file_path)
    module_name = file_path.stem
    
    try:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if not spec or not spec.loader:
            return
        
        module = importlib.util.module_from_spec(spec)
        # Fix relative imports by setting package
        module.__package__ = "unigate.plugins"
        module.__file__ = str(file_path)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type):
                registry.register(attr, "plugin_dir")
    except Exception:
        pass


def resolve_type(type_str: str) -> str:
    """Resolve short type to full type-prefixed name."""
    if "." in type_str:
        return type_str
    
    if type_str in ("telegram", "web", "webui", "whatsapp", "email", "sms", "slack", "discord"):
        return f"channel.{type_str}"
    
    if type_str in ("http", "webhook", "ftp", "sftp", "websocket", "file", "smtp", "smtp_email"):
        return f"transport.{type_str}"
    
    if type_str in ("from", "text_contains", "text_pattern", "sender", "has_media", "day_of_week", "hour_of_day"):
        return f"match.{type_str}"
    
    if type_str in ("truncate", "extract_subject", "add_metadata", "add_timestamp"):
        return f"transform.{type_str}"
    
    return f"channel.{type_str}"
