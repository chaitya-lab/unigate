"""Instance lifecycle orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .channel import BaseChannel
from .lifecycle import HealthStatus, InstanceState, SetupResult, SetupStatus


@dataclass(slots=True)
class InstanceRuntime:
    instance_id: str
    channel: BaseChannel
    state: InstanceState = InstanceState.UNCONFIGURED
    last_error: str | None = None
    retries: int = 0
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class InstanceManager:
    def __init__(self) -> None:
        self.instances: dict[str, InstanceRuntime] = {}

    def register(self, instance_id: str, channel: BaseChannel) -> InstanceRuntime:
        runtime = InstanceRuntime(instance_id=instance_id, channel=channel)
        self.instances[instance_id] = runtime
        return runtime

    async def setup(self, instance_id: str) -> SetupResult:
        runtime = self.instances[instance_id]
        runtime.state = InstanceState.SETTING_UP
        runtime.updated_at = datetime.now(UTC)
        try:
            result = await runtime.channel.setup()
            if result.status is SetupStatus.READY:
                runtime.state = InstanceState.ACTIVE
            elif result.status is SetupStatus.NEEDS_INTERACTION:
                runtime.state = InstanceState.SETUP_REQUIRED
            else:
                runtime.state = InstanceState.DEGRADED
                runtime.last_error = result.message or "setup failed"
            runtime.updated_at = datetime.now(UTC)
            return result
        except Exception as exc:
            runtime.state = InstanceState.DEGRADED
            runtime.last_error = str(exc)
            runtime.updated_at = datetime.now(UTC)
            return SetupResult(status=SetupStatus.FAILED, message=str(exc))

    async def health(self, instance_id: str) -> HealthStatus:
        runtime = self.instances[instance_id]
        try:
            health = await runtime.channel.health_check()
        except Exception:
            runtime.state = InstanceState.RECONNECTING
            runtime.updated_at = datetime.now(UTC)
            return HealthStatus.UNHEALTHY
        if health is HealthStatus.HEALTHY and runtime.state is InstanceState.RECONNECTING:
            runtime.state = InstanceState.ACTIVE
        elif health is not HealthStatus.HEALTHY:
            runtime.state = InstanceState.DEGRADED
        runtime.updated_at = datetime.now(UTC)
        return health

    async def ensure_started(self, instance_id: str) -> None:
        runtime = self.instances[instance_id]
        if runtime.state is not InstanceState.ACTIVE:
            await self.setup(instance_id)
        if runtime.state is InstanceState.ACTIVE:
            await runtime.channel.start()

    async def stop(self, instance_id: str) -> None:
        runtime = self.instances[instance_id]
        await runtime.channel.stop()
        runtime.state = InstanceState.UNCONFIGURED
        runtime.updated_at = datetime.now(UTC)

    def status(self) -> dict[str, dict[str, Any]]:
        return {
            key: {
                "state": runtime.state.value,
                "last_error": runtime.last_error,
                "retries": runtime.retries,
                "updated_at": runtime.updated_at.isoformat(),
            }
            for key, runtime in self.instances.items()
        }
