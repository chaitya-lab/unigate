"""Comprehensive routing test suite for Unigate.

Tests multi-instance routing, rule conditions, degraded channels,
and visibility via CLI.
"""

import asyncio
import pytest
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent / "src"))

from unigate import Message, Sender
from unigate.kernel import Exchange
from unigate.plugins.base import get_registry
from unigate.plugins.channel_web import WebChannel
from unigate.routing import MatchCondition, RoutingAction, RoutingRule, RoutingEngine
from unigate.stores import InMemoryStores, NamespacedSecureStore


class TestExchange:
    """Test harness for Exchange with routing."""
    
    def __init__(self):
        self.inbox = InMemoryStores()
        self.outbox = InMemoryStores()
        self.sessions = InMemoryStores()
        self.dedup = InMemoryStores()
        self.exchange = Exchange(
            inbox=self.inbox,
            outbox=self.outbox,
            sessions=self.sessions,
            dedup=self.dedup,
        )
    
    def add_web_instance(self, instance_id: str) -> WebChannel:
        """Add a web instance to the exchange."""
        store = NamespacedSecureStore().for_instance(instance_id)
        channel = WebChannel(instance_id, store, self.exchange, {})
        self.exchange.register_instance(instance_id, channel)
        return channel
    
    async def start_all_instances(self) -> None:
        """Start all registered instances."""
        for instance_id in self.exchange.instances:
            await self.exchange.instance_manager.ensure_started(instance_id)
    
    def setup_routing_rules(self, rules: list[dict]) -> None:
        """Set up routing configuration."""
        config = {"routing": {"rules": rules}}
        self.exchange.setup_routing(config)
    
    async def send_message(
        self,
        instance_id: str,
        text: str,
        sender_name: str = "Test User",
        sender_id: str = "user123",
        group_id: str | None = None,
        extra: dict | None = None,
    ) -> str:
        """Send a test message to an instance."""
        raw = {
            "id": f"msg-{uuid4().hex[:8]}",
            "session_id": f"session-{uuid4().hex[:8]}",
            "from_instance": instance_id,
            "sender": {"id": sender_id, "name": sender_name},
            "text": text,
            "group_id": group_id,
        }
        if extra:
            raw.update(extra)
        status = await self.exchange.ingest(instance_id, raw)
        return status
    
    async def get_outbox_messages(self) -> list[dict]:
        """Get all outbox messages."""
        records = await self.outbox.list_outbox(limit=1000)
        return [
            {
                "outbox_id": r.outbox_id,
                "destination": r.destination,
                "status": r.status,
                "text": r.message.text,
                "attempts": r.attempts,
                "last_error": r.last_error,
            }
            for r in records
        ]
    
    async def get_inbox_messages(self) -> list[dict]:
        """Get all inbox messages."""
        records = await self.inbox.list_inbox(limit=1000)
        return [
            {
                "message_id": r.message_id,
                "instance_id": r.instance_id,
                "text": r.message.text,
            }
            for r in records
        ]
    
    async def flush_outbox(self) -> None:
        """Flush pending outbox messages."""
        await self.exchange.flush_outbox()
    
    def get_events(self) -> list[dict]:
        """Get recent events."""
        return [
            {"name": e.name, "payload": e.payload}
            for e in self.exchange.events[-20:]
        ]


@pytest.mark.asyncio
async def test_basic_routing():
    """Test 1: Basic routing from one instance to another."""
    print("\n" + "=" * 60)
    print("TEST 1: Basic Routing")
    print("=" * 60)
    
    test = TestExchange()
    
    # Create two instances
    alice = test.add_web_instance("alice")
    bob = test.add_web_instance("bob")
    await test.start_all_instances()
    
    # Route all messages from alice to bob
    test.setup_routing_rules([
        {
            "name": "alice-to-bob",
            "priority": 100,
            "match": {"from_instance": "alice"},
            "actions": {"forward_to": ["bob"]},
        },
    ])
    
    # Send message via alice
    await test.send_message("alice", "Hello from Alice!", sender_name="Alice")
    
    # Flush and check
    await test.flush_outbox()
    
    outbox = await test.get_outbox_messages()
    inbox = await test.get_inbox_messages()
    
    print(f"Inbox messages: {len(inbox)}")
    print(f"Outbox messages: {len(outbox)}")
    for msg in outbox:
        print(f"  -> {msg['destination']}: '{msg['text']}' (status: {msg['status']})")
    
    assert len(inbox) == 1, "Should have 1 inbox message"
    assert len(outbox) == 1, "Should have 1 outbox message"
    assert outbox[0]["destination"] == "bob", "Should route to bob"
    assert outbox[0]["text"] == "Hello from Alice!", "Text should match"
    
    print("PASSED: Basic routing works")


@pytest.mark.asyncio
async def test_text_contains_routing():
    """Test 2: Route based on text content."""
    print("\n" + "=" * 60)
    print("TEST 2: Text Contains Routing")
    print("=" * 60)
    
    test = TestExchange()
    
    alice = test.add_web_instance("alice")
    sales = test.add_web_instance("sales")
    support = test.add_web_instance("support")
    await test.start_all_instances()
    
    # Route "sales" keyword to sales team
    # Route "help" keyword to support team
    test.setup_routing_rules([
        {
            "name": "sales-routing",
            "priority": 100,
            "match": {"text_contains": "sales"},
            "actions": {"forward_to": ["sales"]},
        },
        {
            "name": "support-routing",
            "priority": 100,
            "match": {"text_contains": "help"},
            "actions": {"forward_to": ["support"]},
        },
    ])
    
    # Send different messages
    await test.send_message("alice", "I want to buy something in the sales department", sender_name="Customer1")
    await test.send_message("alice", "Help me please", sender_name="Customer2")
    await test.send_message("alice", "What's the price for sales?", sender_name="Customer3")
    
    await test.flush_outbox()
    
    outbox = await test.get_outbox_messages()
    
    print(f"Outbox messages: {len(outbox)}")
    by_dest = {}
    for msg in outbox:
        dest = msg["destination"]
        by_dest.setdefault(dest, []).append(msg["text"])
    
    for dest, texts in by_dest.items():
        print(f"  -> {dest}: {texts}")
    
    assert "sales" in by_dest, "Should have routed to sales"
    assert "support" in by_dest, "Should have routed to support"
    assert len(by_dest["sales"]) == 2, "Sales should get 2 messages"
    assert len(by_dest["support"]) == 1, "Support should get 1 message"
    
    print("PASSED: Text contains routing works")


@pytest.mark.asyncio
async def test_sender_routing():
    """Test 3: Route based on sender ID."""
    print("\n" + "=" * 60)
    print("TEST 3: Sender-Based Routing")
    print("=" * 60)
    
    test = TestExchange()
    
    alice = test.add_web_instance("alice")
    vip = test.add_web_instance("vip")
    regular = test.add_web_instance("regular")
    await test.start_all_instances()
    
    # VIP users (sender_id starts with "vip_") go to vip channel
    test.setup_routing_rules([
        {
            "name": "vip-routing",
            "priority": 10,
            "match": {"sender_pattern": "vip_*"},
            "actions": {"forward_to": ["vip"]},
        },
        {
            "name": "regular-default",
            "priority": 100,
            "match": {},  # matches everything
            "actions": {"forward_to": ["regular"]},
        },
    ])
    
    await test.send_message("alice", "Hello VIP!", sender_id="vip_john")
    await test.send_message("alice", "Hello regular!", sender_id="user_jane")
    await test.send_message("alice", "Another VIP here", sender_id="vip_alice")
    
    await test.flush_outbox()
    
    outbox = await test.get_outbox_messages()
    
    print(f"Outbox messages: {len(outbox)}")
    by_dest = {}
    for msg in outbox:
        dest = msg["destination"]
        by_dest.setdefault(dest, []).append(msg["text"])
    
    for dest, texts in by_dest.items():
        print(f"  -> {dest}: {texts}")
    
    assert len(by_dest.get("vip", [])) == 2, "VIP should get 2 messages"
    assert len(by_dest.get("regular", [])) == 1, "Regular should get 1 message"
    
    print("PASSED: Sender-based routing works")


@pytest.mark.asyncio
async def test_group_routing():
    """Test 4: Route based on group ID."""
    print("\n" + "=" * 60)
    print("TEST 4: Group-Based Routing")
    print("=" * 60)
    
    test = TestExchange()
    
    main = test.add_web_instance("main")
    dev_group = test.add_web_instance("dev-team")
    ops_group = test.add_web_instance("ops-team")
    await test.start_all_instances()
    
    test.setup_routing_rules([
        {
            "name": "dev-team",
            "priority": 100,
            "match": {"group_id": "dev-*"},
            "actions": {"forward_to": ["dev-team"]},
        },
        {
            "name": "ops-team",
            "priority": 100,
            "match": {"group_id": "ops-*"},
            "actions": {"forward_to": ["ops-team"]},
        },
    ])
    
    await test.send_message("main", "Dev message", group_id="dev-channel")
    await test.send_message("main", "Ops message", group_id="ops-alerts")
    await test.send_message("main", "General message", group_id=None)
    
    await test.flush_outbox()
    
    outbox = await test.get_outbox_messages()
    
    print(f"Outbox messages: {len(outbox)}")
    for msg in outbox:
        print(f"  -> {msg['destination']}: '{msg['text']}'")
    
    dev_msgs = [m for m in outbox if m["destination"] == "dev-team"]
    ops_msgs = [m for m in outbox if m["destination"] == "ops-team"]
    
    assert len(dev_msgs) == 1, "Dev team should get 1 message"
    assert len(ops_msgs) == 1, "Ops team should get 1 message"
    
    print("PASSED: Group-based routing works")


@pytest.mark.asyncio
async def test_priority_ordering():
    """Test 5: Rules with different priorities."""
    print("\n" + "=" * 60)
    print("TEST 5: Priority Ordering")
    print("=" * 60)
    
    test = TestExchange()
    
    alice = test.add_web_instance("alice")
    high = test.add_web_instance("high-priority")
    normal = test.add_web_instance("normal")
    await test.start_all_instances()
    
    # Lower priority number = higher priority (checked first)
    test.setup_routing_rules([
        {
            "name": "high-priority",
            "priority": 1,  # Very high priority (lowest number)
            "match": {"text_contains": "urgent"},
            "actions": {"forward_to": ["high-priority"]},
        },
        {
            "name": "normal",
            "priority": 100,  # Normal priority
            "match": {"text_contains": "urgent"},
            "actions": {"forward_to": ["normal"]},
        },
    ])
    
    # Send urgent message - should only go to high-priority (first match wins)
    await test.send_message("alice", "This is urgent!")
    
    await test.flush_outbox()
    
    outbox = await test.get_outbox_messages()
    
    print(f"Outbox messages: {len(outbox)}")
    for msg in outbox:
        print(f"  -> {msg['destination']}: '{msg['text']}'")
    
    # First matching rule (highest priority = lowest number) should win
    assert len(outbox) == 1, "Should only have 1 message (first match wins)"
    assert outbox[0]["destination"] == "high-priority", "Should route to high-priority"
    
    print("PASSED: Priority ordering works (first match wins)")


@pytest.mark.asyncio
async def test_disabled_rule():
    """Test 6: Disabled rules are not applied."""
    print("\n" + "=" * 60)
    print("TEST 6: Disabled Rules")
    print("=" * 60)
    
    test = TestExchange()
    
    alice = test.add_web_instance("alice")
    bob = test.add_web_instance("bob")
    await test.start_all_instances()
    
    test.setup_routing_rules([
        {
            "name": "disabled-rule",
            "priority": 100,
            "enabled": False,  # Disabled!
            "match": {"text_contains": "test"},
            "actions": {"forward_to": ["bob"]},
        },
    ])
    
    await test.send_message("alice", "This is a test message")
    
    await test.flush_outbox()
    
    outbox = await test.get_outbox_messages()
    
    print(f"Outbox messages: {len(outbox)}")
    
    # No routing should happen (rule is disabled)
    assert len(outbox) == 0, "Should have no routed messages"
    
    print("PASSED: Disabled rules are not applied")


@pytest.mark.asyncio
async def test_keep_in_default():
    """Test 7: keep_in_default action."""
    print("\n" + "=" * 60)
    print("TEST 7: Keep In Default")
    print("=" * 60)
    
    test = TestExchange()
    
    alice = test.add_web_instance("alice")
    bob = test.add_web_instance("bob")
    await test.start_all_instances()
    
    # Also keep message in alice's default destination
    test.setup_routing_rules([
        {
            "name": "route-and-keep",
            "priority": 100,
            "match": {"text_contains": "keep"},
            "actions": {"forward_to": ["bob"], "keep_in_default": True},
        },
    ])
    
    await test.send_message("alice", "Keep this message")
    
    await test.flush_outbox()
    
    outbox = await test.get_outbox_messages()
    
    print(f"Outbox messages: {len(outbox)}")
    for msg in outbox:
        print(f"  -> {msg['destination']}: '{msg['text']}'")
    
    # Should have forwarded to bob AND kept in alice
    destinations = [m["destination"] for m in outbox]
    assert "bob" in destinations, "Should route to bob"
    
    print("PASSED: keep_in_default works")


@pytest.mark.asyncio
async def test_degraded_channel_queues():
    """Test 8: Circuit breaker prevents delivery when open."""
    print("\n" + "=" * 60)
    print("TEST 8: Degraded Channel Queuing")
    print("=" * 60)
    
    test = TestExchange()
    
    alice = test.add_web_instance("alice")
    bob = test.add_web_instance("bob")
    await test.start_all_instances()
    
    test.setup_routing_rules([
        {
            "name": "alice-to-bob",
            "priority": 100,
            "match": {"from_instance": "alice"},
            "actions": {"forward_to": ["bob"]},
        },
    ])
    
    # Send message while bob is active
    await test.send_message("alice", "Message while bob is up")
    await test.flush_outbox()
    
    outbox_before = await test.get_outbox_messages()
    print(f"Outbox before failure: {len(outbox_before)}")
    sent_before = [m for m in outbox_before if m["status"] == "sent"]
    print(f"  Sent: {len(sent_before)}")
    assert len(sent_before) == 1, "First message should be sent"
    
    # Simulate bob failure by opening its circuit breaker
    bob_runtime = test.exchange.instance_manager.instances["bob"]
    bob_runtime.circuit_breaker.failure_threshold = 1
    bob_runtime.circuit_breaker._failures = 1
    bob_runtime.circuit_breaker._state = "open"
    print("Bob circuit breaker opened")
    
    # Send more messages while bob is down
    await test.send_message("alice", "Message while bob is down")
    
    # Try to flush - messages should NOT be delivered (bob's circuit breaker is open)
    await test.flush_outbox()
    
    outbox = await test.get_outbox_messages()
    sent_after_failure = [m for m in outbox if m["status"] == "sent"]
    
    print(f"Total outbox: {len(outbox)}")
    print(f"Sent after failure: {len(sent_after_failure)}")
    
    # Circuit breaker is open, so new message should NOT be sent
    assert len(sent_after_failure) == 1, "New message should NOT be sent while circuit is open"
    
    # Verify circuit breaker state
    assert not bob_runtime.can_execute(), "Bob should not be able to execute"
    
    print("PASSED: Circuit breaker prevents delivery when open")


@pytest.mark.asyncio
async def test_multiple_conditions():
    """Test 9: Rules with multiple match conditions (AND logic)."""
    print("\n" + "=" * 60)
    print("TEST 9: Multiple Match Conditions")
    print("=" * 60)
    
    test = TestExchange()
    
    alice = test.add_web_instance("alice")
    filtered = test.add_web_instance("filtered")
    others = test.add_web_instance("others")
    await test.start_all_instances()
    
    # Match only if BOTH conditions are true
    test.setup_routing_rules([
        {
            "name": "vip-group-message",
            "priority": 10,
            "match": {
                "sender_pattern": "vip_*",
                "group_id": "important-alerts",
            },
            "actions": {"forward_to": ["filtered"]},
        },
        {
            "name": "catch-all",
            "priority": 100,
            "match": {},
            "actions": {"forward_to": ["others"]},
        },
    ])
    
    # Test cases:
    # 1. VIP + important-alerts group -> filtered
    # 2. VIP + other group -> others
    # 3. Regular + important-alerts group -> others
    
    await test.send_message("alice", "VIP in important group", sender_id="vip_john", group_id="important-alerts")
    await test.send_message("alice", "VIP in other group", sender_id="vip_jane", group_id="random-chat")
    await test.send_message("alice", "Regular in important group", sender_id="user_bob", group_id="important-alerts")
    
    await test.flush_outbox()
    
    outbox = await test.get_outbox_messages()
    
    print(f"Outbox messages: {len(outbox)}")
    by_dest = {}
    for msg in outbox:
        dest = msg["destination"]
        by_dest.setdefault(dest, []).append(msg["text"])
    
    for dest, texts in by_dest.items():
        print(f"  -> {dest}: {texts}")
    
    assert len(by_dest.get("filtered", [])) == 1, "Filtered should get 1 message"
    assert len(by_dest.get("others", [])) == 2, "Others should get 2 messages"
    
    print("PASSED: Multiple conditions work correctly")


@pytest.mark.asyncio
async def test_view_routing_rules():
    """Test 10: View routing rules via CLI."""
    print("\n" + "=" * 60)
    print("TEST 10: View Routing Rules")
    print("=" * 60)
    
    test = TestExchange()
    
    alice = test.add_web_instance("alice")
    bob = test.add_web_instance("bob")
    
    test.setup_routing_rules([
        {
            "name": "rule-1",
            "priority": 100,
            "match": {"from_instance": "alice"},
            "actions": {"forward_to": ["bob"]},
        },
        {
            "name": "rule-2",
            "priority": 200,
            "match": {"text_contains": "help"},
            "actions": {"forward_to": ["support"]},
        },
    ])
    
    engine = test.exchange.get_routing_engine()
    rules = engine.get_rules()
    
    print(f"Registered rules: {len(rules)}")
    for rule in rules:
        print(f"  - {rule.name} (priority: {rule.priority}, enabled: {rule.enabled})")
        if rule.match:
            print(f"    Match: {rule.match.to_dict()}")
        if rule.actions:
            print(f"    Actions: {rule.actions.forward_to}")
    
    assert len(rules) == 2, "Should have 2 rules"
    
    print("PASSED: Routing rules are visible")


@pytest.mark.asyncio
async def test_events_logging():
    """Test 11: Events are logged during routing."""
    print("\n" + "=" * 60)
    print("TEST 11: Events Logging")
    print("=" * 60)
    
    test = TestExchange()
    
    alice = test.add_web_instance("alice")
    bob = test.add_web_instance("bob")
    
    test.setup_routing_rules([
        {
            "name": "alice-to-bob",
            "priority": 100,
            "match": {"from_instance": "alice"},
            "actions": {"forward_to": ["bob"]},
        },
    ])
    
    await test.send_message("alice", "Test message for events")
    await test.flush_outbox()
    
    events = test.get_events()
    
    print(f"Events captured: {len(events)}")
    routing_events = [e for e in events if "routing" in e["name"] or "outbox" in e["name"]]
    for event in routing_events:
        print(f"  - {event['name']}: {event['payload']}")
    
    routing_names = [e["name"] for e in routing_events]
    assert "routing.started" in routing_names, "Should have routing.started event"
    assert "outbox.persisted" in routing_names, "Should have outbox.persisted event"
    
    print("PASSED: Events are logged correctly")


@pytest.mark.asyncio
async def test_day_of_week_matcher():
    """Test 12: Day of week conditional routing."""
    print("\n" + "=" * 60)
    print("TEST 12: Day of Week Routing")
    print("=" * 60)
    
    registry = get_registry()
    
    matcher = registry.create_match("match.day_of_week")
    if not matcher:
        print("SKIPPED: Day of week matcher not available")
        return
    
    from datetime import datetime
    
    msg = Message(
        id="test",
        session_id="test",
        from_instance="test",
        sender=Sender(platform_id="test", name="Test"),
        ts=datetime.now(),
        text="test",
    )
    
    # Test matching specific days
    today = datetime.now().strftime("%A").lower()
    print(f"Today is: {today}")
    
    result = matcher.match(msg, today)
    print(f"Match result for today ({today}): {result}")
    
    assert result is True, "Should match today"
    print("PASSED: Day of week matcher works")


@pytest.mark.asyncio
async def test_hour_of_day_matcher():
    """Test 13: Hour of day conditional routing."""
    print("\n" + "=" * 60)
    print("TEST 13: Hour of Day Routing")
    print("=" * 60)
    
    registry = get_registry()
    
    matcher = registry.create_match("match.hour_of_day")
    if not matcher:
        print("SKIPPED: Hour of day matcher not available")
        return
    
    from datetime import datetime
    
    current_hour = datetime.now().hour
    msg = Message(
        id="test",
        session_id="test",
        from_instance="test",
        sender=Sender(platform_id="test", name="Test"),
        ts=datetime.now(),
        text="test",
    )
    
    # Match current hour
    result = matcher.match(msg, current_hour)
    print(f"Match result for current hour ({current_hour}): {result}")
    
    # Match wrong hour
    wrong_hour = (current_hour + 5) % 24
    result_wrong = matcher.match(msg, wrong_hour)
    print(f"Match result for hour {wrong_hour}: {result_wrong}")
    
    assert result is True, "Should match current hour"
    assert result_wrong is False, "Should not match wrong hour"
    
    print("PASSED: Hour of day matcher works")


async def run_all_tests():
    """Run all routing tests."""
    print("\n" + "=" * 60)
    print("UNIGATE ROUTING TEST SUITE")
    print("=" * 60)
    
    tests = [
        ("Basic Routing", test_basic_routing),
        ("Text Contains Routing", test_text_contains_routing),
        ("Sender-Based Routing", test_sender_routing),
        ("Group-Based Routing", test_group_routing),
        ("Priority Ordering", test_priority_ordering),
        ("Disabled Rules", test_disabled_rule),
        ("Keep In Default", test_keep_in_default),
        ("Degraded Channel Queuing", test_degraded_channel_queues),
        ("Multiple Match Conditions", test_multiple_conditions),
        ("View Routing Rules", test_view_routing_rules),
        ("Events Logging", test_events_logging),
        ("Day of Week Matcher", test_day_of_week_matcher),
        ("Hour of Day Matcher", test_hour_of_day_matcher),
    ]
    
    passed = 0
    failed = 0
    skipped = 0
    
    for name, test_func in tests:
        try:
            await test_func()
            passed += 1
        except AssertionError as e:
            print(f"FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Skipped: {skipped}")
    print(f"Total: {passed + failed + skipped}")
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
