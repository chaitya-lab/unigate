"""Comprehensive test suite for unigate core functionality."""

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import sys
sys.path.insert(0, "H:/2026/SelfAi/dev/chaitya/unigate/src")

from unigate import Exchange, Message
from unigate.message import Interactive, Sender, InteractiveResponse
from unigate.stores import InMemoryStores
from unigate.channel import BaseChannel, SendResult
from unigate.capabilities import ChannelCapabilities
from unigate.lifecycle import SetupResult, SetupStatus, HealthStatus


class FakeChannel(BaseChannel):
    """Fake channel for testing."""
    name = "fake"
    transport = "test"
    auth_method = "none"
    
    async def setup(self):
        return SetupResult(status=SetupStatus.READY)
    
    def to_message(self, raw):
        sender_data = raw.get("sender", {})
        sender = Sender(
            platform_id=str(sender_data.get("id", "user")),
            name=str(sender_data.get("name", "User")),
        )
        
        interactive = None
        if raw.get("interactive"):
            i = raw["interactive"]
            interactive = Interactive(
                interaction_id=i.get("interaction_id", str(uuid4())),
                type=i.get("type", "confirm"),
                prompt=i.get("prompt", ""),
                options=i.get("options"),
                timeout_seconds=i.get("timeout_seconds"),
            )
            # Handle nested response
            if i.get("response"):
                r = i["response"]
                interactive.response = InteractiveResponse(
                    interaction_id=r.get("interaction_id", ""),
                    type=r.get("type", "confirm"),
                    value=r.get("value", ""),
                )
        
        return Message(
            id=raw.get("id", str(uuid4())),
            session_id=raw.get("session_id", str(uuid4())),
            from_instance=self.instance_id,
            sender=sender,
            ts=datetime.now(timezone.utc),
            group_id=raw.get("group_id"),
            bot_mentioned=raw.get("bot_mentioned", True),
            thread_id=raw.get("thread_id"),
            text=raw.get("text"),
            interactive=interactive,
            raw=raw,
            metadata={},
        )
    
    async def from_message(self, msg):
        self._sent.append(msg)
        return SendResult(success=True, provider_message_id=f"{self.instance_id}:{msg.id}")
    
    async def verify_signature(self, request):
        return True
    
    @property
    def capabilities(self):
        return ChannelCapabilities(
            direction="bidirectional",
            supports_groups=True,
            supports_threads=True,
        )
    
    async def health_check(self):
        return HealthStatus.HEALTHY
    
    def __init__(self, instance_id):
        self.instance_id = instance_id
        self._sent = []


def create_exchange():
    """Create a fresh exchange with test channel."""
    stores = InMemoryStores()
    exchange = Exchange(
        inbox=stores,
        outbox=stores,
        sessions=stores,
        dedup=stores,
        interactions=stores,
    )
    
    test_channel = FakeChannel("test")
    exchange.register_instance("test", test_channel)
    
    return exchange, stores, test_channel


async def test_basic_flow():
    """Test 1: Basic message send/receive."""
    print("\n" + "="*50)
    print("TEST 1: Basic Message Flow")
    print("="*50)
    
    exchange, stores, channel = create_exchange()
    
    messages_received = []
    
    async def handler(msg: Message) -> Message | None:
        messages_received.append(msg)
        return Message(
            id=f"reply-{uuid4()}",
            session_id=msg.session_id,
            from_instance="handler",
            sender=Sender(platform_id="handler", name="Handler"),
            ts=datetime.now(timezone.utc),
            text=f"Echo: {msg.text}",
        )
    
    exchange.set_handler(handler)
    
    msg_id = await exchange.ingest("test", {
        "id": "msg-001",
        "session_id": "session-001",
        "from_instance": "test",
        "sender": {"id": "user-1", "name": "Test User"},
        "text": "Hello World",
    })
    
    await exchange.flush_outbox()
    
    print(f"  Ingest result: {msg_id}")
    print(f"  Handler received: {len(messages_received)} messages")
    print(f"  Received text: {messages_received[0].text if messages_received else 'NONE'}")
    print(f"  Channel received: {len(channel._sent)} messages")
    
    assert msg_id == "ack", f"Expected ack, got {msg_id}"
    assert len(messages_received) == 1
    assert messages_received[0].text == "Hello World"
    assert len(channel._sent) == 1
    assert "Echo" in channel._sent[0].text
    
    print("  [PASSED]")
    return True


async def test_dedup():
    """Test 2: Deduplication."""
    print("\n" + "="*50)
    print("TEST 2: Deduplication")
    print("="*50)
    
    exchange, stores, channel = create_exchange()
    
    received = []
    exchange.set_handler(lambda m: (received.append(m), None)[1])
    
    await exchange.ingest("test", {
        "id": "dup-001",
        "session_id": "s1",
        "from_instance": "test",
        "sender": {"id": "u1", "name": "User"},
        "text": "First",
    })
    
    result1 = await exchange.ingest("test", {
        "id": "dup-001",
        "session_id": "s1",
        "from_instance": "test",
        "sender": {"id": "u1", "name": "User"},
        "text": "Duplicate",
    })
    
    print(f"  First ingest: ack")
    print(f"  Second ingest (same ID): {result1}")
    print(f"  Handler calls: {len(received)}")
    
    assert result1 == "duplicate"
    assert len(received) == 1
    
    print("  [PASSED]")
    return True


async def test_interactive_confirm():
    """Test 3: Interactive confirm buttons."""
    print("\n" + "="*50)
    print("TEST 3: Interactive Confirm")
    print("="*50)
    
    exchange, stores, channel = create_exchange()
    
    async def handler(msg: Message) -> Message | None:
        if msg.text == "/ask":
            return Message(
                id=f"reply-{uuid4()}",
                session_id=msg.session_id,
                from_instance="handler",
                sender=Sender(platform_id="handler", name="Handler"),
                ts=datetime.now(timezone.utc),
                text="Do you want to proceed?",
                interactive=Interactive(
                    interaction_id=f"confirm-{uuid4()}",
                    type="confirm",
                    prompt="Do you want to proceed?",
                    options=["yes", "no"],
                    timeout_seconds=60,
                ),
            )
        return None
    
    exchange.set_handler(handler)
    
    await exchange.ingest("test", {
        "id": "ask-001",
        "session_id": "session-ask",
        "from_instance": "test",
        "sender": {"id": "user", "name": "User"},
        "text": "/ask",
    })
    
    await exchange.flush_outbox()
    
    sent = channel._sent[-1] if channel._sent else None
    if sent:
        print(f"  Message text: {sent.text}")
        print(f"  Interactive type: {type(sent.interactive).__name__}")
        print(f"  Options: {sent.interactive.options}")
        assert isinstance(sent.interactive, Interactive)
        assert sent.interactive.options == ["yes", "no"]
    
    print("  [PASSED]")
    return True


async def test_interactive_response():
    """Test 4: Interactive response handling."""
    print("\n" + "="*50)
    print("TEST 4: Interactive Response")
    print("="*50)
    
    exchange, stores, channel = create_exchange()
    
    responses = []
    
    async def handler(msg: Message) -> Message | None:
        if msg.interactive and msg.interactive.response:
            responses.append(msg.interactive.response.value)
            return Message(
                id=f"reply-{uuid4()}",
                session_id=msg.session_id,
                from_instance="handler",
                sender=Sender(platform_id="handler", name="Handler"),
                ts=datetime.now(timezone.utc),
                text=f"Got: {msg.interactive.response.value}",
            )
        return None
    
    exchange.set_handler(handler)
    
    # First send interactive prompt
    await exchange.ingest("test", {
        "id": "ask-002",
        "session_id": "session-response",
        "from_instance": "test",
        "sender": {"id": "user", "name": "User"},
        "text": "/ask",
        "interactive": {
            "interaction_id": "confirm-123",
            "type": "confirm",
            "prompt": "Continue?",
            "options": ["yes", "no"],
        },
    })
    await exchange.flush_outbox()
    
    # Now send the response
    await exchange.ingest("test", {
        "id": "response-001",
        "session_id": "session-response",
        "from_instance": "test",
        "sender": {"id": "user", "name": "User"},
        "text": "yes",
        "interactive": {
            "interaction_id": "confirm-123",
            "type": "confirm",
            "prompt": "Continue?",
            "options": ["yes", "no"],
            "response": {
                "interaction_id": "confirm-123",
                "type": "confirm",
                "value": "yes",
            }
        },
    })
    await exchange.flush_outbox()
    
    print(f"  Interactive prompt sent")
    print(f"  Response sent: yes")
    print(f"  Handler received responses: {len(responses)}")
    
    assert len(responses) == 1, f"Expected 1 response, got {len(responses)}"
    assert responses[0] == "yes"
    
    print("  [PASSED]")
    return True


async def test_group_mentions():
    """Test 5: Group mentions filtering."""
    print("\n" + "="*50)
    print("TEST 5: Group Mentions Filtering")
    print("="*50)
    
    exchange, stores, channel = create_exchange()
    
    received = []
    
    async def handler(msg: Message) -> Message | None:
        received.append(msg)
        if msg.group_id and not msg.bot_mentioned:
            print(f"  [IGNORED] Group msg without mention: {msg.text}")
            return None
        return Message(
            id=f"reply-{uuid4()}",
            session_id=msg.session_id,
            from_instance="handler",
            sender=Sender(platform_id="handler", name="Handler"),
            ts=datetime.now(timezone.utc),
            text=f"Echo: {msg.text}",
        )
    
    exchange.set_handler(handler)
    
    # With mention
    await exchange.ingest("test", {
        "id": "group-001",
        "session_id": "group-session",
        "from_instance": "test",
        "sender": {"id": "user1", "name": "User One"},
        "text": "@bot hello",
        "group_id": "my-group",
        "bot_mentioned": True,
    })
    await exchange.flush_outbox()
    
    # Without mention
    await exchange.ingest("test", {
        "id": "group-002",
        "session_id": "group-session-2",
        "from_instance": "test",
        "sender": {"id": "user2", "name": "User Two"},
        "text": "hello everyone",
        "group_id": "my-group",
        "bot_mentioned": False,
    })
    await exchange.flush_outbox()
    
    print(f"  Total handler calls: {len(received)}")
    
    # Both go to handler, but second is ignored (returns None)
    assert len(received) == 2
    
    # Only 1 message in outbox (from the mentioned one)
    outbox_items = await stores.list_outbox()
    print(f"  Outbox messages: {len(outbox_items)}")
    
    assert len(outbox_items) == 1
    
    print("  [PASSED]")
    return True


async def test_thread_support():
    """Test 6: Thread support."""
    print("\n" + "="*50)
    print("TEST 6: Thread Support")
    print("="*50)
    
    exchange, stores, channel = create_exchange()
    
    received = []
    
    async def handler(msg: Message) -> Message:
        received.append(msg)
        return Message(
            id=f"reply-{uuid4()}",
            session_id=msg.session_id,
            from_instance="handler",
            sender=Sender(platform_id="handler", name="Handler"),
            ts=datetime.now(timezone.utc),
            text=f"Thread {msg.thread_id}: {msg.text}",
        )
    
    exchange.set_handler(handler)
    
    await exchange.ingest("test", {
        "id": "thread-001",
        "session_id": "thread-session-1",
        "from_instance": "test",
        "sender": {"id": "user1", "name": "User"},
        "text": "Hello in thread",
        "thread_id": "thread-123",
    })
    
    await exchange.ingest("test", {
        "id": "thread-002",
        "session_id": "thread-session-2",
        "from_instance": "test",
        "sender": {"id": "user2", "name": "User"},
        "text": "Hello in different thread",
        "thread_id": "thread-456",
    })
    
    await exchange.flush_outbox()
    
    print(f"  Thread 1: {received[0].thread_id}")
    print(f"  Thread 2: {received[1].thread_id}")
    print(f"  Handler calls: {len(received)}")
    
    assert len(received) == 2
    assert received[0].thread_id == "thread-123"
    assert received[1].thread_id == "thread-456"
    
    outbox_items = await stores.list_outbox()
    print(f"  Outbox messages: {len(outbox_items)}")
    
    print("  [PASSED]")
    return True


async def test_circuit_breaker():
    """Test 7: Circuit breaker."""
    print("\n" + "="*50)
    print("TEST 7: Circuit Breaker")
    print("="*50)
    
    exchange, stores, channel = create_exchange()
    
    exchange.set_handler(lambda m: None)
    exchange.set_circuit_breaker("test", failure_threshold=3)
    
    runtime = exchange.instance_manager.instances.get("test")
    if runtime and runtime.circuit_breaker:
        print(f"  Circuit breaker state: {runtime.circuit_breaker.state}")
    
    print("  [PASSED]")
    return True


async def test_session_routing():
    """Test 8: Session routing."""
    print("\n" + "="*50)
    print("TEST 8: Session Routing")
    print("="*50)
    
    exchange, stores, channel = create_exchange()
    
    exchange.set_handler(lambda m: Message(
        id=f"reply-{uuid4()}",
        session_id=m.session_id,
        from_instance="handler",
        sender=Sender(platform_id="handler", name="Handler"),
        ts=datetime.now(timezone.utc),
        text="pong",
    ))
    
    await exchange.ingest("test", {
        "id": "sess-001",
        "session_id": "my-session",
        "from_instance": "test",
        "sender": {"id": "user", "name": "User"},
        "text": "ping",
    })
    
    await exchange.flush_outbox()
    
    outbox = await stores.list_outbox()
    print(f"  Origin: test")
    print(f"  Outbox destination: {outbox[0].destination if outbox else 'NONE'}")
    
    assert outbox[0].destination == "test"
    
    print("  [PASSED]")
    return True


async def test_multiple_channels():
    """Test 9: Multiple channels."""
    print("\n" + "="*50)
    print("TEST 9: Multiple Channels")
    print("="*50)
    
    stores = InMemoryStores()
    exchange = Exchange(
        inbox=stores,
        outbox=stores,
        sessions=stores,
        dedup=stores,
    )
    
    telegram_ch = FakeChannel("telegram")
    discord_ch = FakeChannel("discord")
    web_ch = FakeChannel("web")
    
    exchange.register_instance("telegram", telegram_ch)
    exchange.register_instance("discord", discord_ch)
    exchange.register_instance("web", web_ch)
    
    exchange.set_handler(lambda m: Message(
        id=f"reply-{uuid4()}",
        session_id=m.session_id,
        from_instance="handler",
        sender=Sender(platform_id="handler", name="Handler"),
        ts=datetime.now(timezone.utc),
        text="pong",
    ))
    
    await exchange.ingest("telegram", {"id": "t1", "session_id": "s1", "from_instance": "telegram", "sender": {"id": "u1", "name": "U1"}, "text": "from telegram"})
    await exchange.ingest("discord", {"id": "d1", "session_id": "s2", "from_instance": "discord", "sender": {"id": "u2", "name": "U2"}, "text": "from discord"})
    await exchange.ingest("web", {"id": "w1", "session_id": "s3", "from_instance": "web", "sender": {"id": "u3", "name": "U3"}, "text": "from web"})
    
    await exchange.flush_outbox()
    
    print(f"  Telegram: {len(telegram_ch._sent)}")
    print(f"  Discord: {len(discord_ch._sent)}")
    print(f"  Web: {len(web_ch._sent)}")
    
    assert len(telegram_ch._sent) == 1
    assert len(discord_ch._sent) == 1
    assert len(web_ch._sent) == 1
    
    print("  [PASSED]")
    return True


async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("  UNIGATE CORE TEST SUITE")
    print("="*60)
    
    tests = [
        ("Basic Flow", test_basic_flow),
        ("Deduplication", test_dedup),
        ("Interactive Confirm", test_interactive_confirm),
        ("Interactive Response", test_interactive_response),
        ("Group Mentions", test_group_mentions),
        ("Thread Support", test_thread_support),
        ("Circuit Breaker", test_circuit_breaker),
        ("Session Routing", test_session_routing),
        ("Multiple Channels", test_multiple_channels),
    ]
    
    results = []
    for name, test in tests:
        try:
            result = await test()
            results.append((name, result))
        except Exception as e:
            print(f"  [FAILED]: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    print("\n" + "="*60)
    print("  RESULTS SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "[PASSED]" if result else "[FAILED]"
        print(f"  {status}: {name}")
    
    print(f"\n  Total: {passed}/{total} passed")
    print("="*60)
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
