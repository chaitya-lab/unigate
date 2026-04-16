"""Tests for plugin system."""

import pytest
from datetime import datetime, timezone

from unigate import Message, Sender
from unigate.plugins.base import get_registry, PluginRegistry


class TestPluginRegistry:
    """Test unified plugin registry."""

    def test_registry_singleton(self):
        registry1 = get_registry()
        registry2 = get_registry()
        assert registry1 is registry2

    def test_registry_has_channels(self):
        registry = get_registry()
        assert "web" in registry.channels
        assert "telegram" in registry.channels

    def test_registry_has_matchers(self):
        registry = get_registry()
        assert "from" in registry.matches
        assert "text_contains" in registry.matches
        assert "sender" in registry.matches
        assert "has_media" in registry.matches
        assert "day_of_week" in registry.matches

    def test_registry_has_transforms(self):
        registry = get_registry()
        assert "truncate" in registry.transforms
        assert "extract_subject" in registry.transforms
        assert "add_metadata" in registry.transforms

    def test_registry_has_transports(self):
        registry = get_registry()
        assert "http" in registry.transports

    def test_create_match(self):
        registry = get_registry()
        matcher = registry.create_match("from")
        assert matcher is not None

    def test_create_transform(self):
        registry = get_registry()
        transform = registry.create_transform("truncate")
        assert transform is not None
