"""Unified plugin system for unigate.

All plugins operate on the universal Message format.
Plugin types: channel, match, transform, transport
Naming: type.name (e.g., channel.telegram, match.text_contains)

Plugins are loaded via get_registry() from plugin_dirs in config:
    
    unigate:
      plugin_dirs:
        - ./src/unigate/plugins  # built-in plugins
        - ./my_custom_plugins   # your own plugins
"""

from .base import (
    PluginRegistry,
    PluginEntry,
    PluginStatus,
    PluginType,
    ChannelPlugin,
    MatcherPlugin,
    TransformPlugin,
    TransportPlugin,
    get_registry,
    register_plugin_dirs,
    resolve_type,
)

# Re-export common plugins for convenience
from .channel_telegram import TelegramChannel, TelegramChannelPlugin
from .channel_web import WebChannel, WebChannelPlugin, APIKeyWebChannel, BearerTokenWebChannel
from .channel_webui import WebUIChannel
from .channel_fake_sms import FakeSMSChannel
from .match_from import FromMatcher, FromPatternMatcher
from .match_text import TextContainsMatcher, TextPatternMatcher, TextStartsWithMatcher, IsCommandMatcher, SubjectContainsMatcher
from .match_sender import SenderMatcher, SenderPatternMatcher, SenderNameMatcher, SenderDomainMatcher
from .match_media import HasMediaMatcher, HasAttachmentMatcher, HasImageMatcher, HasVideoMatcher, MediaTypeMatcher
from .match_time import DayOfWeekMatcher, HourOfDayMatcher, TimeRangeMatcher
from .transform_truncate import TruncateTransform, Truncate160Transform
from .transform_extract import ExtractSubjectTransform, EmailSubjectOnlyTransform, ExtractPatternTransform
from .transform_add import AddMetadataTransform, AddTimestampTransform, AddPrefixTransform, AddSenderTransform, AddTagTransform
from .transform_case import UppercaseTransform, LowercaseTransform, TitleCaseTransform
from .transport_http import HTTPTransport, WebhookTransport
from .transport_websocket import WebSocketTransport
from .transport_ftp import FTPTransport, SFTPTransport, FileTransport

__all__ = [
    "PluginRegistry",
    "PluginEntry",
    "PluginStatus",
    "PluginType",
    "ChannelPlugin",
    "MatcherPlugin",
    "TransformPlugin",
    "TransportPlugin",
    "get_registry",
    "register_plugin_dirs",
    "resolve_type",
    "TelegramChannel",
    "TelegramChannelPlugin",
    "WebChannel",
    "WebChannelPlugin",
    "APIKeyWebChannel",
    "BearerTokenWebChannel",
    "WebUIChannel",
    "FakeSMSChannel",
    "FromMatcher",
    "FromPatternMatcher",
    "TextContainsMatcher",
    "TextPatternMatcher",
    "TextStartsWithMatcher",
    "IsCommandMatcher",
    "SubjectContainsMatcher",
    "SenderMatcher",
    "SenderPatternMatcher",
    "SenderNameMatcher",
    "SenderDomainMatcher",
    "HasMediaMatcher",
    "HasAttachmentMatcher",
    "HasImageMatcher",
    "HasVideoMatcher",
    "MediaTypeMatcher",
    "DayOfWeekMatcher",
    "HourOfDayMatcher",
    "TimeRangeMatcher",
    "TruncateTransform",
    "Truncate160Transform",
    "ExtractSubjectTransform",
    "EmailSubjectOnlyTransform",
    "ExtractPatternTransform",
    "AddMetadataTransform",
    "AddTimestampTransform",
    "AddPrefixTransform",
    "AddSenderTransform",
    "AddTagTransform",
    "UppercaseTransform",
    "LowercaseTransform",
    "TitleCaseTransform",
    "HTTPTransport",
    "WebhookTransport",
    "WebSocketTransport",
    "FTPTransport",
    "SFTPTransport",
    "FileTransport",
]