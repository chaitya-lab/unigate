"""Tests for plugin system."""

import pytest
from datetime import datetime, timezone

from unigate import Message, Sender
from unigate.plugins.base import get_registry, PluginRegistry, resolve_type


class TestPluginRegistry:
    """Test unified plugin registry."""

    @pytest.fixture(autouse=True)
    def load_plugins(self):
        """Load plugins before each test."""
        from unigate.plugins.base import register_plugin_dirs
        import os
        # From tests/ directory, go up to project root, then to src/unigate/plugins
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        plugin_path = os.path.join(root, "src", "unigate", "plugins")
        if os.path.isdir(plugin_path) and "channel_webui.py" in os.listdir(plugin_path):
            register_plugin_dirs([plugin_path])

    def test_registry_singleton(self):
        registry1 = get_registry()
        registry2 = get_registry()
        assert registry1 is registry2

    def test_registry_has_channels(self):
        registry = get_registry()
        assert "channel.webui" in registry.channels
        assert "channel.telegram" in registry.channels
        assert "channel.whatsapp" in registry.channels

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
        assert "transport.websocket" in registry.transports
        assert "transport.ftp" in registry.transports
        assert "transport.sftp" in registry.transports
        assert "transport.file" in registry.transports

    def test_create_match(self):
        registry = get_registry()
        matcher = registry.create_match("match.from")
        assert matcher is not None

    def test_create_transform(self):
        registry = get_registry()
        transform = registry.create_transform("transform.truncate")
        assert transform is not None

    def test_enable_plugin(self):
        registry = get_registry()
        registry.disable("channel.telegram")
        assert not registry.channels["channel.telegram"].enabled
        registry.enable("channel.telegram")
        assert registry.channels["channel.telegram"].enabled

    def test_disable_plugin(self):
        registry = get_registry()
        registry.disable("channel.telegram")
        assert not registry.channels["channel.telegram"].enabled

    def test_get_channel(self):
        registry = get_registry()
        registry.enable("telegram")
        cls = registry.get_channel("telegram")
        assert cls is not None
        cls = registry.get_channel("channel.telegram")
        assert cls is not None

    def test_list_plugins(self):
        registry = get_registry()
        plugins = registry.list_plugins()
        assert len(plugins) > 0
        types = set(p.type for p in plugins)
        assert "channel" in types
        assert "match" in types
        assert "transform" in types
        assert "transport" in types

    def test_generate_config(self):
        registry = get_registry()
        config = registry.generate_config()
        assert "plugins" in config
        assert "enabled" in config["plugins"]
        assert len(config["plugins"]["enabled"]) > 0

    def test_validate_plugins(self):
        registry = get_registry()
        valid, missing = registry.validate_plugins(["match.from", "nonexistent"])
        assert "match.from" in valid
        assert "nonexistent" in missing


class TestResolveType:
    """Test type resolution."""

    def test_resolve_channel_short(self):
        assert resolve_type("telegram") == "channel.telegram"
        assert resolve_type("whatsapp") == "channel.whatsapp"
        assert resolve_type("web") == "channel.web"

    def test_resolve_transport_short(self):
        assert resolve_type("http") == "transport.http"
        assert resolve_type("websocket") == "transport.websocket"
        assert resolve_type("ftp") == "transport.ftp"
        assert resolve_type("sftp") == "transport.sftp"
        assert resolve_type("file") == "transport.file"

    def test_resolve_match_short(self):
        assert resolve_type("from") == "match.from"
        assert resolve_type("text_contains") == "match.text_contains"

    def test_resolve_transform_short(self):
        assert resolve_type("truncate") == "transform.truncate"
        assert resolve_type("add_metadata") == "transform.add_metadata"

    def test_resolve_already_full(self):
        assert resolve_type("channel.telegram") == "channel.telegram"
        assert resolve_type("transport.http") == "transport.http"


class TestWhatsAppPlugin:
    """Test WhatsApp channel plugin."""

    def test_whatsapp_plugin_registered(self):
        registry = get_registry()
        assert "channel.whatsapp" in registry.channels

    @pytest.mark.asyncio
    async def test_whatsapp_receive(self):
        from unigate.plugins.channel_whatsapp import WhatsAppChannelPlugin
        plugin = WhatsAppChannelPlugin()
        
        raw = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "id": "msg123",
                            "from": "1234567890",
                            "type": "text",
                            "text": {"body": "Hello"}
                        }],
                        "contacts": [{
                            "profile": {"name": "Test User"}
                        }]
                    }
                }]
            }]
        }
        
        msg = await plugin.receive(raw)
        assert msg is not None
        assert msg.text == "Hello"
        assert msg.sender.platform_id == "1234567890"

    @pytest.mark.asyncio
    async def test_whatsapp_receive_image(self):
        from unigate.plugins.channel_whatsapp import WhatsAppChannelPlugin
        plugin = WhatsAppChannelPlugin()
        
        raw = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "id": "msg456",
                            "from": "9876543210",
                            "type": "image"
                        }],
                        "contacts": [{}]
                    }
                }]
            }]
        }
        
        msg = await plugin.receive(raw)
        assert msg is not None
        assert msg.text == "[Image]"

