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
        assert "channel.web" in registry.channels
        assert "channel.telegram" in registry.channels

    def test_registry_has_matchers(self):
        registry = get_registry()
        assert "match.from" in registry.matches
        assert "match.text_contains" in registry.matches
        assert "match.sender" in registry.matches
        assert "match.has_media" in registry.matches
        assert "match.day_of_week" in registry.matches

    def test_registry_has_transforms(self):
        registry = get_registry()
        assert "transform.truncate" in registry.transforms
        assert "transform.extract_subject" in registry.transforms
        assert "transform.add_metadata" in registry.transforms

    def test_registry_has_transports(self):
        registry = get_registry()
        assert "transport.http" in registry.transports

    def test_create_match(self):
        registry = get_registry()
        matcher = registry.create_match("match.from")
        assert matcher is not None

    def test_create_transform(self):
        registry = get_registry()
        transform = registry.create_transform("transform.truncate")
        assert transform is not None
