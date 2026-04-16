"""Public package surface for the 1.5 rewrite."""

from .capabilities import ChannelCapabilities
from .adapters import FakeWebhookAdapter, InternalAdapter
from .channel import BaseChannel, KernelHandle, RawRequest, SecureStore, SendResult
from .channels import APIKeyWebChannel, BearerTokenWebChannel, TelegramChannel, WebChannel
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
from .registry import PluginRegistry, get_registry, register_plugin_dirs
from .resilience import CircuitBreaker, CircuitState, RetryPolicy
from .routing import RoutingEngine, RoutingRule, MatchCondition, RoutingAction
from .routing.matchers import (
    get_matcher_registry,
    MatcherRegistry,
    RoutingMatcher,
)
from .routing.matchers.base import RoutingMatcher
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
from .transforms import (
    TransformExtension,
    TransformRegistry,
    get_transform_registry,
)
from .transports import (
    TransportProtocol,
    TransportRegistry,
    get_transport_registry,
)

__all__ = [
    "__version__",
    "Action",
    "APIKeyWebChannel",
    "BaseChannel",
    "BearerTokenWebChannel",
    "ChannelCapabilities",
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
    "get_matcher_registry",
    "get_registry",
    "get_transform_registry",
    "get_transport_registry",
    "HealthStatus",
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
    "MatcherRegistry",
    "MatchCondition",
    "MediaRef",
    "MediaType",
    "Message",
    "NamespacedSecureStore",
    "OutboxRecord",
    "OutboundExtension",
    "PendingInteractionRecord",
    "PluginRegistry",
    "RawRequest",
    "Reaction",
    "RegisteredInstance",
    "register_plugin_dirs",
    "RetryPolicy",
    "RoutingAction",
    "RoutingEngine",
    "RoutingMatcher",
    "RoutingRule",
    "SecureStore",
    "SendResult",
    "Sender",
    "SetupResult",
    "SetupStatus",
    "SQLiteStores",
    "TelegramChannel",
    "TestKit",
    "TransformExtension",
    "TransformRegistry",
    "TransportProtocol",
    "TransportRegistry",
    "Unigate",
    "UnigateASGIApp",
    "WebChannel",
    "main",
]

__version__ = "0.2.0a0"
