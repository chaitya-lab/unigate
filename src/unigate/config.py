"""Config loading and runtime construction."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .channels import ApiChannel, InternalChannel, WebChannel, WebSocketServerChannel
from .gate import Unigate


def load_config(path: str | Path) -> dict[str, Any]:
    """Load config from JSON, TOML, or YAML when PyYAML is available."""

    config_path = Path(path).expanduser().resolve()
    suffix = config_path.suffix.lower()
    raw_text = config_path.read_text(encoding="utf-8")

    if suffix == ".json":
        data = json.loads(raw_text)
    elif suffix == ".toml":
        import tomllib

        data = tomllib.loads(raw_text)
    elif suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:
            raise RuntimeError("YAML config requires PyYAML to be installed.") from exc
        data = yaml.safe_load(raw_text)
    else:
        raise ValueError(f"Unsupported config format: {suffix}")

    if not isinstance(data, dict):
        raise ValueError("Config root must be a mapping.")
    return _resolve_env(data)


def build_gate_from_config(path: str | Path) -> tuple[Unigate, dict[str, Any]]:
    """Build a gate and register declared instances from a config file."""

    config = load_config(path)
    settings = config.get("unigate", {})
    if not isinstance(settings, dict):
        raise ValueError("`unigate` config section must be a mapping.")

    storage = _string_setting(settings, "storage", default="memory")
    sqlite_path = settings.get("sqlite_path")
    resolved_sqlite_path: str | None
    if sqlite_path is None:
        resolved_sqlite_path = None
    else:
        resolved_sqlite_path = _resolve_relative_path(Path(path), str(sqlite_path))

    gate = Unigate(storage=storage, sqlite_path=resolved_sqlite_path)

    instances = config.get("instances", {})
    if not isinstance(instances, dict):
        raise ValueError("`instances` config section must be a mapping.")

    for instance_id, instance_config in instances.items():
        if not isinstance(instance_id, str):
            raise ValueError("Instance ids must be strings.")
        if not isinstance(instance_config, dict):
            raise ValueError(f"Instance config for {instance_id!r} must be a mapping.")
        channel_type = _string_setting(instance_config, "type")
        gate.register_instance(instance_id, _build_channel(channel_type))

    return gate, config


def describe_config(config: dict[str, Any]) -> dict[str, Any]:
    """Produce a small stable summary for CLI output."""

    settings = config.get("unigate", {})
    instances = config.get("instances", {})
    if not isinstance(settings, dict):
        settings = {}
    if not isinstance(instances, dict):
        instances = {}

    return {
        "storage": settings.get("storage", "memory"),
        "sqlite_path": settings.get("sqlite_path"),
        "asgi_prefix": settings.get("asgi_prefix", "/unigate"),
        "host": settings.get("host", "127.0.0.1"),
        "port": settings.get("port", 8000),
        "instances": {
            instance_id: instance_config.get("type")
            for instance_id, instance_config in instances.items()
            if isinstance(instance_config, dict)
        },
    }


def _build_channel(channel_type: str) -> object:
    if channel_type == "api":
        return ApiChannel()
    if channel_type == "web":
        return WebChannel()
    if channel_type == "websocket_server":
        return WebSocketServerChannel()
    if channel_type == "internal":
        return InternalChannel()
    raise ValueError(f"Unsupported instance type: {channel_type}")


def _string_setting(data: dict[str, Any], key: str, *, default: str | None = None) -> str:
    value = data.get(key, default)
    if not isinstance(value, str):
        raise ValueError(f"{key!r} must be a string.")
    return value


def _resolve_env(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _resolve_env(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_env(item) for item in value]
    if isinstance(value, str):
        return os.path.expandvars(value)
    return value


def _resolve_relative_path(config_path: Path, path_value: str) -> str:
    path = Path(path_value).expanduser()
    if path.is_absolute():
        return str(path)
    return str((config_path.parent / path).resolve())
