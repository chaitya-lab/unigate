"""Instance registry and lifecycle state for the minimum runtime."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .channel import BaseChannel


class InstanceState(str, Enum):
    """Minimum instance lifecycle states."""

    UNCONFIGURED = "unconfigured"
    ACTIVE = "active"
    STOPPED = "stopped"


@dataclass(slots=True)
class InstanceRecord:
    """Registered channel instance."""

    instance_id: str
    channel_type: str
    channel: BaseChannel
    state: InstanceState = InstanceState.UNCONFIGURED


class InstanceRegistry:
    """Tracks registered channel instances."""

    def __init__(self) -> None:
        self._instances: dict[str, InstanceRecord] = {}

    def add(self, instance_id: str, channel: BaseChannel) -> InstanceRecord:
        record = InstanceRecord(
            instance_id=instance_id,
            channel_type=channel.channel_type,
            channel=channel,
            state=InstanceState.ACTIVE,
        )
        self._instances[instance_id] = record
        return record

    def get(self, instance_id: str) -> InstanceRecord:
        return self._instances[instance_id]
