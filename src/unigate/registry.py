"""Plugin discovery for channels and extensions."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any


CHANNEL_ENTRY_POINT = "unigate.channels"
EXTENSION_ENTRY_POINT = "unigate.extensions"


def _get_entry_points(group: str) -> dict[str, Any]:
    try:
        import importlib.metadata
        eps = importlib.metadata.entry_points()
        group_eps = eps.select(group=group)
        return {ep.name: ep for ep in group_eps}
    except Exception:
        return {}


def _load_from_entry_point(name: str) -> type | None:
    eps = _get_entry_points(CHANNEL_ENTRY_POINT)
    if name in eps:
        return eps[name].load()
    eps = _get_entry_points(EXTENSION_ENTRY_POINT)
    if name in eps:
        return eps[name].load()
    return None


def _scan_directory(path: Path) -> list[type]:
    found: list[type] = []
    if not path.is_dir():
        return found
    for file_path in path.iterdir():
        if file_path.suffix == ".py" and not file_path.name.startswith("_"):
            module_name = file_path.stem
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec and spec.loader:
                try:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if isinstance(attr, type) and hasattr(attr, "__name__"):
                            if attr is not _get_subclass_check(attr, "BaseChannel") or attr is not _get_subclass_check(attr, "BaseExtension"):
                                try:
                                    from ..channel import BaseChannel
                                    from ..extensions import InboundExtension, OutboundExtension, EventExtension
                                    if issubclass(attr, BaseChannel):
                                        found.append(attr)
                                    if issubclass(attr, (InboundExtension, OutboundExtension, EventExtension)):
                                        found.append(attr)
                                except ImportError:
                                    pass
                except Exception:
                    pass
    return found


def _get_subclass_check(cls: type, base_name: str) -> type | None:
    try:
        if base_name == "BaseChannel":
            from ..channel import BaseChannel
            if issubclass(cls, BaseChannel):
                return cls
        elif base_name == "BaseExtension":
            from ..extensions import InboundExtension, OutboundExtension, EventExtension
            if issubclass(cls, (InboundExtension, OutboundExtension, EventExtension)):
                return cls
    except ImportError:
        pass
    return None


class PluginRegistry:
    def __init__(self) -> None:
        self.channels: dict[str, type] = {}
        self.extensions: dict[str, type] = {}

    def register_channel(self, channel_cls: type) -> None:
        name = getattr(channel_cls, "name", None)
        if name:
            self.channels[name] = channel_cls

    def register_extension(self, ext_cls: type) -> None:
        name = getattr(ext_cls, "name", None)
        if name:
            self.extensions[name] = ext_cls

    def load_from_entry_points(self) -> None:
        for group, attr_name in [(CHANNEL_ENTRY_POINT, "channels"), (EXTENSION_ENTRY_POINT, "extensions")]:
            eps = _get_entry_points(group)
            for name, ep in eps.items():
                try:
                    cls = ep.load()
                    if attr_name == "channels":
                        self.register_channel(cls)
                    else:
                        self.register_extension(cls)
                except Exception:
                    pass

    def load_from_directories(self, directories: list[str]) -> None:
        for dir_path in directories:
            path = Path(dir_path)
            if not path.exists():
                continue
            for cls in _scan_directory(path):
                from ..channel import BaseChannel
                from ..extensions import InboundExtension, OutboundExtension, EventExtension
                if issubclass(cls, BaseChannel):
                    self.register_channel(cls)
                elif issubclass(cls, (InboundExtension, OutboundExtension, EventExtension)):
                    self.register_extension(cls)

    def get_channel(self, name: str) -> type | None:
        return self.channels.get(name)

    def get_extension(self, name: str) -> type | None:
        return self.extensions.get(name)


_global_registry: PluginRegistry | None = None


def get_registry() -> PluginRegistry:
    global _global_registry
    if _global_registry is None:
        _global_registry = PluginRegistry()
        _global_registry.load_from_entry_points()
    return _global_registry


def register_plugin_dirs(directories: list[str]) -> None:
    registry = get_registry()
    registry.load_from_directories(directories)
