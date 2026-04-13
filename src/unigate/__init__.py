"""unigate public package."""

from .asgi import UnigateASGIApp, create_asgi_app
from .channel import ChannelCapabilities, HealthStatus, SetupResult, SetupStatus
from .channels import ApiChannel, InternalChannel, WebChannel, WebSocketServerChannel
from .config import build_gate_from_config, load_config
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
    "UnigateASGIApp",
    "UniversalMessage",
    "WebChannel",
    "WebSocketServerChannel",
    "build_gate_from_config",
    "create_asgi_app",
    "load_config",
]

__version__ = "0.1.0a0"
