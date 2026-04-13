"""unigate public package."""

from .channel import ChannelCapabilities, HealthStatus, SetupResult, SetupStatus
from .channels import ApiChannel, InternalChannel, WebChannel, WebSocketServerChannel
from .envelope import OutboundMessage, SenderProfile, UniversalMessage
from .gate import Unigate
from .interactive import InteractivePayload, InteractiveResponse, InteractionType

__all__ = [
    "__version__",
    "ChannelCapabilities",
    "HealthStatus",
    "ApiChannel",
    "InternalChannel",
    "InteractivePayload",
    "InteractiveResponse",
    "InteractionType",
    "OutboundMessage",
    "SenderProfile",
    "SetupResult",
    "SetupStatus",
    "Unigate",
    "UniversalMessage",
    "WebChannel",
    "WebSocketServerChannel",
]

__version__ = "0.1.0a0"
