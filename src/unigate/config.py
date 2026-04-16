"""Configuration loading with !env interpolation."""

from __future__ import annotations

import os
import re
from typing import Any


ENV_PATTERN = re.compile(r"!env:(\w+)")


def _interpolate_env(value: str | None) -> str | None:
    """Replace !env:VAR_NAME with the environment variable value."""
    if value is None:
        return None
    match = ENV_PATTERN.match(value)
    if match:
        var_name = match.group(1)
        return os.environ.get(var_name, "")
    return value


def _process_config(obj: Any) -> Any:
    """Recursively process config dict/list to interpolate env vars."""
    if isinstance(obj, dict):
        return {k: _process_config(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_process_config(item) for item in obj]
    if isinstance(obj, str):
        return _interpolate_env(obj)
    return obj


def load_config(config: dict[str, Any]) -> dict[str, Any]:
    """Load and process a configuration dictionary."""
    return _process_config(config)


def load_yaml(path: str) -> dict[str, Any]:
    """Load configuration from a YAML file."""
    import yaml
    with open(path) as f:
        config = yaml.safe_load(f)
    return load_config(config)
