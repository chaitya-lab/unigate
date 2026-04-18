"""Lifecycle and health types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class InstanceState(str, Enum):
    """Instance lifecycle states."""

    UNCONFIGURED = "unconfigured"
    SETUP_REQUIRED = "setup_required"
    SETTING_UP = "setting_up"
    ACTIVE = "active"
    DEGRADED = "degraded"
    RECONNECTING = "reconnecting"
    DISABLED = "disabled"


class HealthStatus(str, Enum):
    """Instance health results."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class SetupStatus(str, Enum):
    """Setup outcomes."""

    READY = "ready"
    NEEDS_INTERACTION = "needs_interaction"
    FAILED = "failed"


@dataclass(slots=True)
class SetupResult:
    """Result returned by channel setup."""

    status: SetupStatus
    interaction_type: str | None = None
    interaction_data: dict[str, Any] = field(default_factory=dict)
    message: str | None = None
