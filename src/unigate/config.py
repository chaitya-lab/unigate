"""Configuration loading with !env interpolation and !include support.

Features:
- !env:VAR_NAME - Replace with environment variable
- !include:path/to/file.yaml - Include external file
- _file: references - Reference external config files
- enabled: true/false - Enable/disable instances and rules
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any


ENV_PATTERN = re.compile(r"!env:(\w+)")
INCLUDE_PATTERN = re.compile(r"!include:(\S+)")


def _interpolate_env(value: str | None) -> str | None:
    """Replace !env:VAR_NAME with the environment variable value."""
    if value is None:
        return None
    match = ENV_PATTERN.match(value)
    if match:
        var_name = match.group(1)
        return os.environ.get(var_name, "")
    return value


def _preprocess_yaml(content: str) -> str:
    """Pre-process YAML content to replace !env:VAR and !include:path."""
    base_dir = Path.cwd()
    
    def replace_env(match):
        var_name = match.group(1)
        return os.environ.get(var_name, "")
    
    content = re.sub(ENV_PATTERN, replace_env, content)
    
    def replace_include(match):
        include_path = match.group(1)
        try:
            inc_path = Path(include_path)
            if not inc_path.is_absolute():
                inc_path = base_dir / inc_path
            if inc_path.exists():
                return inc_path.read_text(encoding='utf-8')
            else:
                print(f"[CONFIG] Warning: include file not found: {include_path}")
                return ""
        except Exception as e:
            print(f"[CONFIG] Warning: failed to include {include_path}: {e}")
            return ""
    
    content = re.sub(INCLUDE_PATTERN, replace_include, content)
    return content


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
    """Load configuration from a YAML file.
    
    Supports:
    - !env:VAR - Environment variables
    - !include:path - Include external files
    - *_file: references - External config files
    - enabled: true/false - Enable/disable
    """
    import yaml
    
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = Path.cwd() / file_path
    
    with open(file_path) as f:
        content = f.read()
    
    content = _preprocess_yaml(content)
    config = yaml.safe_load(content) or {}
    config = _process_config(config)
    
    config = _merge_file_references(config, file_path.parent)
    
    return config


def _merge_file_references(config: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    """Merge configurations from external file references.
    
    Supported references:
    - instances_file: path/to/instances.yaml
    - routing_file: path/to/routing.yaml
    - extensions_file: path/to/extensions.yaml
    """
    result = dict(config)
    
    file_keys = ['instances_file', 'routing_file', 'extensions_file']
    
    for key in file_keys:
        if key in result:
            ref_path = result.pop(key)
            if ref_path:
                ref_file = Path(ref_path)
                if not ref_file.is_absolute():
                    ref_file = base_dir / ref_file
                
                if ref_file.exists():
                    try:
                        with open(ref_file) as f:
                            content = _preprocess_yaml(f.read())
                        import yaml
                        ref_config = yaml.safe_load(content) or {}
                        ref_config = _process_config(ref_config)
                        
                        section = key.replace('_file', '')
                        if section in ref_config:
                            if section not in result:
                                result[section] = {}
                            result[section].update(ref_config[section])
                        else:
                            result.update(ref_config)
                    except Exception as e:
                        print(f"[CONFIG] Warning: failed to load {ref_path}: {e}")
    
    return result


def filter_by_enabled(items: dict[str, Any]) -> dict[str, Any]:
    """Filter dict to only include items where enabled != false.
    
    Items without 'enabled' key are included by default.
    Items with 'enabled: true' or 'enabled: no_value' are included.
    Items with 'enabled: false' are excluded.
    """
    result = {}
    for key, value in items.items():
        if not isinstance(value, dict):
            result[key] = value
            continue
        
        enabled = value.get('enabled', True)
        if enabled is False or enabled == 'false':
            continue
        result[key] = value
    
    return result


__all__ = [
    "load_config",
    "load_yaml",
    "filter_by_enabled",
    "ENV_PATTERN",
    "INCLUDE_PATTERN",
]