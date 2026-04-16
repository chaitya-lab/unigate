"""Instance lifecycle orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable

from .channel import BaseChannel
from .lifecycle import HealthStatus, InstanceState, SetupResult, SetupStatus
from .resilience import CircuitBreaker


StateChangeCallback = Callable[[str, str, str], None]


@dataclass(slots=True)
class InstanceRuntime:
    instance_id: str
    channel: BaseChannel
    state: InstanceState = InstanceState.UNCONFIGURED
    last_error: str | None = None
    retries: int = 0
    max_attempts: int = 5
    retry_base_seconds: int = 2
    retry_max_seconds: int = 30
    fallback_instances: list[str] = field(default_factory=list)
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    circuit_breaker: CircuitBreaker = field(default_factory=CircuitBreaker)
    _on_state_change: StateChangeCallback | None = field(default=None, repr=False)

    def _notify_state_change(self, old_state: str, new_state: str) -> None:
        if self._on_state_change and old_state != new_state:
            self._on_state_change(self.instance_id, old_state, new_state)

    def record_success(self) -> None:
        old_state = self.state.value
        self.circuit_breaker.record_success()
        if self.circuit_breaker.state.value == "closed":
            self.state = InstanceState.ACTIVE
        self._notify_state_change(old_state, self.state.value)

    def record_failure(self) -> None:
        old_state = self.state.value
        self.circuit_breaker.record_failure()
        if self.circuit_breaker.state.value == "open":
            self.state = InstanceState.DEGRADED
        self._notify_state_change(old_state, self.state.value)

    def can_execute(self) -> bool:
        return self.circuit_breaker.can_execute()
    
    def get_next_fallback(self, tried: set[str]) -> str | None:
        """Get next available fallback instance."""
        for fallback_id in self.fallback_instances:
            if fallback_id not in tried:
                return fallback_id
        return None


class InstanceManager:
    def __init__(self) -> None:
        self.instances: dict[str, InstanceRuntime] = {}
        self._on_state_change: StateChangeCallback | None = None
    
    def set_state_change_callback(self, callback: StateChangeCallback) -> None:
        """Set callback for state changes."""
        self._on_state_change = callback
        for runtime in self.instances.values():
            runtime._on_state_change = callback

    def register(
        self,
        instance_id: str,
        channel: BaseChannel,
        *,
        max_attempts: int = 5,
        retry_base_seconds: int = 2,
        retry_max_seconds: int = 30,
        fallback_instances: list[str] | None = None,
    ) -> InstanceRuntime:
        runtime = InstanceRuntime(
            instance_id=instance_id,
            channel=channel,
            max_attempts=max_attempts,
            retry_base_seconds=retry_base_seconds,
            retry_max_seconds=retry_max_seconds,
            fallback_instances=fallback_instances or [],
            _on_state_change=self._on_state_change,
        )
        self.instances[instance_id] = runtime
        return runtime

    async def setup(self, instance_id: str) -> SetupResult:
        runtime = self.instances[instance_id]
        old_state = runtime.state.value
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
            runtime._notify_state_change(old_state, runtime.state.value)
            return result
        except Exception as exc:
            runtime.state = InstanceState.DEGRADED
            runtime.last_error = str(exc)
            runtime.updated_at = datetime.now(UTC)
            runtime._notify_state_change(old_state, runtime.state.value)
            return SetupResult(status=SetupStatus.FAILED, message=str(exc))

    async def health(self, instance_id: str) -> HealthStatus:
        runtime = self.instances[instance_id]
        old_state = runtime.state.value
        try:
            health = await runtime.channel.health_check()
        except Exception:
            runtime.state = InstanceState.RECONNECTING
            runtime.updated_at = datetime.now(UTC)
            runtime._notify_state_change(old_state, runtime.state.value)
            return HealthStatus.UNHEALTHY
        if health is HealthStatus.HEALTHY and runtime.state is InstanceState.RECONNECTING:
            runtime.state = InstanceState.ACTIVE
        elif health is not HealthStatus.HEALTHY:
            runtime.state = InstanceState.DEGRADED
        runtime.updated_at = datetime.now(UTC)
        runtime._notify_state_change(old_state, runtime.state.value)
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
        old_state = runtime.state.value
        runtime.state = InstanceState.UNCONFIGURED
        runtime.updated_at = datetime.now(UTC)
        runtime._notify_state_change(old_state, runtime.state.value)

    def status(self) -> dict[str, dict[str, Any]]:
        return {
            key: {
                "state": runtime.state.value,
                "last_error": runtime.last_error,
                "retries": runtime.retries,
                "max_attempts": runtime.max_attempts,
                "retry_base_seconds": runtime.retry_base_seconds,
                "retry_max_seconds": runtime.retry_max_seconds,
                "fallback_instances": runtime.fallback_instances,
                "circuit_breaker_state": runtime.circuit_breaker.state.value,
                "updated_at": runtime.updated_at.isoformat(),
            }
            for key, runtime in self.instances.items()
        }
