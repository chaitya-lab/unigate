"""Built-in channel adapters."""

from .telegram import TelegramChannel
from .web import APIKeyWebChannel, BearerTokenWebChannel, WebChannel
from .webui import WebUIChannel

__all__ = ["APIKeyWebChannel", "BearerTokenWebChannel", "TelegramChannel", "WebChannel", "WebUIChannel"]
