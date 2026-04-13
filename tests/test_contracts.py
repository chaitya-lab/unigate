from datetime import UTC, datetime
import unittest

from unigate.channel import ChannelCapabilities, HealthStatus, SetupResult, SetupStatus
from unigate.envelope import OutboundMessage, SenderProfile, UniversalMessage
from unigate.interactive import InteractivePayload, InteractionType


class ContractTests(unittest.TestCase):
    def test_universal_message_defaults(self) -> None:
        message = UniversalMessage(
            id="msg-1",
            channel_message_id="platform-1",
            instance_id="internal_app",
            channel_type="internal",
            session_id="session-1",
            sender=SenderProfile(platform_id="user-1", name="User"),
            ts=datetime.now(UTC),
        )

        self.assertTrue(message.bot_mentioned)
        self.assertEqual(message.media, [])
        self.assertEqual(message.envelope_version, "1.0")

    def test_outbound_message_targets_single_instance(self) -> None:
        outbound = OutboundMessage(
            destination_instance_id="support_telegram",
            session_id="session-1",
            outbound_id="out-1",
            text="hello",
        )

        self.assertEqual(outbound.destination_instance_id, "support_telegram")
        self.assertEqual(outbound.text, "hello")

    def test_interactive_payload_can_hold_response_context(self) -> None:
        interactive = InteractivePayload(
            interaction_id="int-1",
            type=InteractionType.CONFIRM,
            prompt="Proceed?",
            context={"source": "test"},
        )

        self.assertEqual(interactive.type, "confirm")
        self.assertEqual(interactive.context["source"], "test")

    def test_channel_contract_value_objects(self) -> None:
        capabilities = ChannelCapabilities(supports_interactive=True, supports_webhooks=True)
        setup = SetupResult(status=SetupStatus.REQUIRED, interaction_type="qr")

        self.assertTrue(capabilities.supports_interactive)
        self.assertTrue(capabilities.supports_webhooks)
        self.assertIs(setup.status, SetupStatus.REQUIRED)
        self.assertEqual(HealthStatus.HEALTHY.value, "healthy")


if __name__ == "__main__":
    unittest.main()
