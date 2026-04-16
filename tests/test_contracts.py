from datetime import UTC, datetime
import unittest

from unigate import (
    Action,
    ChannelCapabilities,
    HealthStatus,
    InstanceManager,
    InstanceState,
    Interactive,
    InteractionType,
    MediaRef,
    MediaType,
    Message,
    Sender,
    SetupResult,
    SetupStatus,
)
from unigate.adapters import InternalAdapter
from unigate.stores import NamespacedSecureStore


class ContractTests(unittest.IsolatedAsyncioTestCase):
    def test_universal_message_shape(self) -> None:
        message = Message(
            id="msg-1",
            session_id="session-1",
            from_instance="telegram_sales",
            sender=Sender(platform_id="user-1", name="User One"),
            ts=datetime.now(UTC),
            to=["handler"],
            text="hello",
            media=[MediaRef(media_id="m1", type=MediaType.IMAGE)],
            actions=[Action(type="typing_on")],
        )
        self.assertEqual(message.from_instance, "telegram_sales")
        self.assertEqual(message.to, ["handler"])
        self.assertEqual(message.media[0].type, MediaType.IMAGE)
        self.assertEqual(message.actions[0].type, "typing_on")

    def test_interactive_payload_shape(self) -> None:
        interactive = Interactive(
            interaction_id="int-1",
            type=InteractionType.CONFIRM,
            prompt="Proceed?",
            context={"source": "test"},
        )
        self.assertEqual(interactive.type, "confirm")
        self.assertEqual(interactive.context["source"], "test")

    async def test_instance_lifecycle_transitions(self) -> None:
        manager = InstanceManager()
        store = NamespacedSecureStore()
        adapter = InternalAdapter("inst", store.for_instance("inst"), kernel=None)
        manager.register("inst", adapter)
        result = await manager.setup("inst")
        self.assertEqual(result.status, SetupStatus.READY)
        self.assertEqual(manager.instances["inst"].state, InstanceState.ACTIVE)
        health = await manager.health("inst")
        self.assertEqual(health, HealthStatus.HEALTHY)

    def test_capabilities_and_setup_types(self) -> None:
        capabilities = ChannelCapabilities(direction="bidirectional", supports_groups=True)
        setup = SetupResult(status=SetupStatus.READY)
        self.assertEqual(capabilities.direction, "bidirectional")
        self.assertTrue(capabilities.supports_groups)
        self.assertIs(setup.status, SetupStatus.READY)
        self.assertEqual(HealthStatus.HEALTHY.value, "healthy")
