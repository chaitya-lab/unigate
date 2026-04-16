"""Public package surface for the 1.5 rewrite."""

from .capabilities import ChannelCapabilities
from .adapters import FakeWebhookAdapter, InternalAdapter
from .channel import BaseChannel, KernelHandle, RawRequest, SecureStore, SendResult
from .cli import main
from .extensions import EventExtension, ExtensionDecision, InboundExtension, OutboundExtension
from .events import KernelEvent
from .instance_manager import InstanceManager, InstanceRuntime
from .kernel import Exchange, RegisteredInstance
from .lifecycle import HealthStatus, InstanceState, SetupResult, SetupStatus
from .message import (
    Action,
    FormField,
    Interactive,
    InteractiveResponse,
    InteractionType,
    MediaRef,
    MediaType,
    Message,
    Reaction,
    Sender,
)
from .runtime import UnigateASGIApp
from .stores import (
    DeadLetterRecord,
    InboxRecord,
    InMemorySecureStore,
    InMemoryStores,
    NamespacedSecureStore,
    OutboxRecord,
    SQLiteStores,
)

__all__ = [
    "__version__",
    "Action",
    "FakeWebhookAdapter",
    "BaseChannel",
    "ChannelCapabilities",
    "EventExtension",
    "ExtensionDecision",
    "Exchange",
    "DeadLetterRecord",
    "InMemorySecureStore",
    "InMemoryStores",
    "FormField",
    "HealthStatus",
    "InboundExtension",
    "InstanceManager",
    "InstanceState",
    "InstanceRuntime",
    "InternalAdapter",
    "InboxRecord",
    "Interactive",
    "InteractiveResponse",
    "InteractionType",
    "KernelEvent",
    "KernelHandle",
    "MediaRef",
    "MediaType",
    "Message",
    "NamespacedSecureStore",
    "OutboxRecord",
    "OutboundExtension",
    "RawRequest",
    "Reaction",
    "RegisteredInstance",
    "SendResult",
    "SQLiteStores",
    "SecureStore",
    "Sender",
    "SetupResult",
    "SetupStatus",
    "UnigateASGIApp",
    "main",
]

__version__ = "0.2.0a0"
