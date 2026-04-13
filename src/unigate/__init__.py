"""unigate public package."""

from .channel import ChannelCapabilities, HealthStatus, SetupResult, SetupStatus
from .envelope import OutboundMessage, SenderProfile, UniversalMessage
from .interactive import InteractivePayload, InteractiveResponse, InteractionType

__all__ = [
    "__version__",
    "ChannelCapabilities",
    "HealthStatus",
    "InteractivePayload",
    "InteractiveResponse",
    "InteractionType",
    "OutboundMessage",
    "SenderProfile",
    "SetupResult",
    "SetupStatus",
    "UniversalMessage",
]

__version__ = "0.1.0a0"
