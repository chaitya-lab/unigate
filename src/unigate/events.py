"""Kernel event model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class KernelEvent:
    """Operational event emitted by the exchange."""

    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    ts: datetime = field(default_factory=lambda: datetime.now(UTC))
