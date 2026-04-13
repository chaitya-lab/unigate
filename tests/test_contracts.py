from datetime import datetime, UTC

from unigate.channel import ChannelCapabilities, HealthStatus, SetupResult, SetupStatus
from unigate.envelope import OutboundMessage, SenderProfile, UniversalMessage
from unigate.interactive import InteractivePayload, InteractionType


def test_universal_message_defaults() -> None:
    message = UniversalMessage(
        id="msg-1",
        channel_message_id="platform-1",
        instance_id="internal_app",
        channel_type="internal",
        session_id="session-1",
        sender=SenderProfile(platform_id="user-1", name="User"),
        ts=datetime.now(UTC),
    )

    assert message.bot_mentioned is True
    assert message.media == []
    assert message.envelope_version == "1.0"


def test_outbound_message_targets_single_instance() -> None:
    outbound = OutboundMessage(
        destination_instance_id="support_telegram",
        session_id="session-1",
        outbound_id="out-1",
        text="hello",
    )

    assert outbound.destination_instance_id == "support_telegram"
    assert outbound.text == "hello"


def test_interactive_payload_can_hold_response_context() -> None:
    interactive = InteractivePayload(
        interaction_id="int-1",
        type=InteractionType.CONFIRM,
        prompt="Proceed?",
        context={"source": "test"},
    )

    assert interactive.type == "confirm"
    assert interactive.context["source"] == "test"


def test_channel_contract_value_objects() -> None:
    capabilities = ChannelCapabilities(supports_interactive=True, supports_webhooks=True)
    setup = SetupResult(status=SetupStatus.REQUIRED, interaction_type="qr")

    assert capabilities.supports_interactive is True
    assert capabilities.supports_webhooks is True
    assert setup.status is SetupStatus.REQUIRED
    assert HealthStatus.HEALTHY.value == "healthy"
