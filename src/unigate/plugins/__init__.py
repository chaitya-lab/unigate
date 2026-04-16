"""Unified plugin system for unigate.

All plugins operate on the universal Message format.
Plugin types: channel, match, transform, transport
"""

from .base import (
    PluginRegistry,
    PluginType,
    ChannelPlugin,
    MatcherPlugin,
    TransformPlugin,
    TransportPlugin,
    get_registry,
    register_plugin_dirs,
)
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

__all__ = [
    "PluginRegistry",
    "PluginType",
    "ChannelPlugin",
    "MatcherPlugin",
    "TransformPlugin",
    "TransportPlugin",
    "get_registry",
    "register_plugin_dirs",
    "WebChannelPlugin",
    "TelegramChannelPlugin",
    "FromMatcher",
    "TextContainsMatcher",
    "TextPatternMatcher",
    "SenderMatcher",
    "SenderPatternMatcher",
    "HasMediaMatcher",
    "HasAttachmentMatcher",
    "DayOfWeekMatcher",
    "HourOfDayMatcher",
    "TruncateTransform",
    "ExtractSubjectTransform",
    "AddMetadataTransform",
    "AddTimestampTransform",
    "HTTPTransport",
]

__version__ = "0.1.0"
