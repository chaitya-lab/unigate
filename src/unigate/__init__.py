"""Public package surface for the 1.5 rewrite."""

from .capabilities import ChannelCapabilities
from .adapters import FakeWebhookAdapter, InternalAdapter
from .channel import BaseChannel, KernelHandle, RawRequest, SecureStore, SendResult
from .cli import main
from .config import load_config, load_yaml
from .extensions import (
    EventExtension,
    ExtensionDecision,
    InboundExtension,
    OutboundExtension,
    create_extension,
)
from .events import KernelEvent
from .gate import Unigate
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
from .plugins import (
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
    TelegramChannel,
    WebChannel,
    APIKeyWebChannel,
    BearerTokenWebChannel,
    WebUIChannel,
    FromMatcher,
    TextContainsMatcher,
    SenderMatcher,
    HasMediaMatcher,
    TruncateTransform,
    ExtractSubjectTransform,
    AddMetadataTransform,
    HTTPTransport,
)
from .resilience import CircuitBreaker, CircuitState, RetryPolicy
from .routing import RoutingEngine, RoutingRule, MatchCondition, RoutingAction, RuleMatcher
from .runtime import UnigateASGIApp
from .stores import (
    DeadLetterRecord,
    InMemorySecureStore,
    InMemoryStores,
    InteractionStore,
    NamespacedSecureStore,
    OutboxRecord,
    PendingInteractionRecord,
    SQLiteStores,
)
from .testing import FakeChannel, TestKit
from .stores import (
    DeadLetterRecord,
    InMemorySecureStore,
    InMemoryStores,
    InteractionStore,
    NamespacedSecureStore,
    OutboxRecord,
    PendingInteractionRecord,
    SQLiteStores,
)
from .testing import FakeChannel, TestKit

__all__ = [
    "__version__",
    "Action",
    "APIKeyWebChannel",
    "BaseChannel",
    "BearerTokenWebChannel",
    "ChannelCapabilities",
    "ChannelPlugin",
    "CircuitBreaker",
    "CircuitState",
    "create_extension",
    "DeadLetterRecord",
    "EventExtension",
    "Exchange",
    "ExtensionDecision",
    "FakeChannel",
    "FakeWebhookAdapter",
    "FormField",
    "FromMatcher",
    "get_registry",
    "HealthStatus",
    "HTTPTransport",
    "InMemorySecureStore",
    "InMemoryStores",
    "InboundExtension",
    "InstanceManager",
    "InstanceRuntime",
    "InstanceState",
    "InternalAdapter",
    "InboxRecord",
    "Interactive",
    "InteractiveResponse",
    "InteractionStore",
    "InteractionType",
    "KernelEvent",
    "KernelHandle",
    "load_config",
    "load_yaml",
    "MatcherPlugin",
    "MatchCondition",
    "MediaRef",
    "MediaType",
    "Message",
    "NamespacedSecureStore",
    "OutboxRecord",
    "OutboundExtension",
    "PendingInteractionRecord",
    "PluginRegistry",
    "PluginType",
    "RawRequest",
    "Reaction",
    "RegisteredInstance",
    "register_plugin_dirs",
    "RetryPolicy",
    "RoutingAction",
    "RoutingEngine",
    "RoutingRule",
    "SecureStore",
    "SendResult",
    "Sender",
    "SenderMatcher",
    "SetupResult",
    "SetupStatus",
    "SQLiteStores",
    "TelegramChannel",
    "TestKit",
    "TransformPlugin",
    "TransportPlugin",
    "Unigate",
    "UnigateASGIApp",
    "WebChannel",
    "WebUIChannel",
    "main",
]

__version__ = "0.2.0a0"
