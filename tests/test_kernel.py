from datetime import UTC, datetime
import unittest

from unigate import (
    BaseChannel,
    ChannelCapabilities,
    Exchange,
    HealthStatus,
    Message,
    Sender,
    SetupResult,
    SetupStatus,
)


class DummyChannel(BaseChannel):
    name = "dummy"
    transport = "stdio"
    auth_method = "none"

    def __init__(self) -> None:
        self.instance_id = "dummy"
        self.config = {}
        self.store = None  # type: ignore[assignment]
        self.kernel = None  # type: ignore[assignment]

    async def setup(self) -> SetupResult:
        return SetupResult(status=SetupStatus.READY)

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    def to_message(self, raw: dict) -> Message:
        return Message(
            id="msg-1",
            platform_id=raw.get("id"),
            session_id="session-1",
            from_instance=self.instance_id,
            sender=Sender(platform_id="user-1", name="User"),
            ts=datetime.now(UTC),
        )

    async def from_message(self, msg: Message) -> None:
        return None

    @property
    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(direction="bidirectional")

    async def health_check(self) -> HealthStatus:
        return HealthStatus.HEALTHY


class KernelTests(unittest.TestCase):
    def test_exchange_registers_instances(self) -> None:
        exchange = Exchange()
        channel = DummyChannel()

        exchange.register_instance("dummy_one", channel)

        self.assertIn("dummy_one", exchange.instances)
        self.assertEqual(exchange.instances["dummy_one"].channel.name, "dummy")


if __name__ == "__main__":
    unittest.main()
