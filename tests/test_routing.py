"""Tests for routing system."""

import asyncio
from datetime import datetime, timezone

import pytest

from unigate.message import Message, Sender
from unigate.routing import MatchCondition, RoutingAction, RoutingEngine, RoutingRule, RuleMatcher, load_rules_from_config


class FakeChannel:
    name = "fake"
    
    def to_message(self, raw):
        sender = Sender(
            platform_id=raw.get("sender_id", "user1"),
            name=raw.get("sender_name", "User"),
        )
        return Message(
            id=raw.get("id", "msg-1"),
            session_id=raw.get("session_id", "sess-1"),
            from_instance=raw.get("from_instance", "telegram"),
            sender=sender,
            ts=datetime.now(timezone.utc),
            text=raw.get("text", ""),
            group_id=raw.get("group_id"),
            thread_id=raw.get("thread_id"),
            media=raw.get("media", []),
            raw=raw,
            metadata=raw.get("metadata", {}),
        )


class FakeExchange:
    def __init__(self):
        self._handler = None
        self.instances = {}
    
    def set_handler(self, handler):
        self._handler = handler


class TestRuleMatcher:
    """Tests for RuleMatcher."""
    
    def test_match_channel(self):
        msg = Message(
            id="1",
            session_id="s1",
            from_instance="telegram",
            sender=Sender(platform_id="u1", name="User"),
            ts=datetime.now(timezone.utc),
        )
        
        assert RuleMatcher.match_channel(msg, "telegram") is True
        assert RuleMatcher.match_channel(msg, "email") is False
        assert RuleMatcher.match_channel(msg, None) is True
    
    def test_match_glob(self):
        assert RuleMatcher.match_glob("user@email.com", "*@email.com") is True
        assert RuleMatcher.match_glob("other@email.com", "*@email.com") is True
        assert RuleMatcher.match_glob("user@other.com", "*@email.com") is False
        assert RuleMatcher.match_glob(None, "*") is False
    
    def test_match_contains(self):
        assert RuleMatcher.match_contains("Hello World", "world") is True
        assert RuleMatcher.match_contains("Hello World", "HELLO") is True  # case insensitive
        assert RuleMatcher.match_contains("Hello World", "foo") is False
        assert RuleMatcher.match_contains(None, "test") is False
    
    def test_match_message_with_conditions(self):
        msg = Message(
            id="1",
            session_id="s1",
            from_instance="telegram",
            sender=Sender(platform_id="user123", name="Test User"),
            ts=datetime.now(timezone.utc),
            text="Help me please",
            group_id="support-123",
        )
        
        # Empty condition matches everything
        condition = MatchCondition()
        assert RuleMatcher.match_message(msg, condition) is True
        
        # from_channel match
        condition = MatchCondition(from_channel="telegram")
        assert RuleMatcher.match_message(msg, condition) is True
        
        condition = MatchCondition(from_channel="email")
        assert RuleMatcher.match_message(msg, condition) is False
        
        # text_contains
        condition = MatchCondition(text_contains="help")
        assert RuleMatcher.match_message(msg, condition) is True
        
        condition = MatchCondition(text_contains="urgent")
        assert RuleMatcher.match_message(msg, condition) is False
        
        # group_id_pattern
        condition = MatchCondition(group_id_pattern="support-*")
        assert RuleMatcher.match_message(msg, condition) is True
        
        condition = MatchCondition(group_id_pattern="admin-*")
        assert RuleMatcher.match_message(msg, condition) is False
        
        # has_media
        condition = MatchCondition(has_media=False)
        assert RuleMatcher.match_message(msg, condition) is True


class TestRoutingRule:
    """Tests for RoutingRule."""
    
    def test_rule_from_dict(self):
        data = {
            "name": "test_rule",
            "priority": 50,
            "enabled": True,
            "match": {
                "from_channel": "telegram",
                "text_contains": "help",
            },
            "actions": {
                "forward_to": ["handler", "telegram_archive"],
                "extensions": ["email_subject_only"],
                "keep_in_default": False,
            },
        }
        
        rule = RoutingRule.from_dict(data)
        
        assert rule.name == "test_rule"
        assert rule.priority == 50
        assert rule.enabled is True
        assert rule.match.from_channel == "telegram"
        assert rule.match.text_contains == "help"
        assert rule.actions.forward_to == ["handler", "telegram_archive"]
        assert rule.actions.extensions == ["email_subject_only"]
    
    def test_rule_matches_message(self):
        data = {
            "name": "support_rule",
            "priority": 10,
            "match": {
                "from_channel": "telegram",
                "group_id_pattern": "support-*",
            },
            "actions": {
                "forward_to": ["handler"],
            },
        }
        
        rule = RoutingRule.from_dict(data)
        
        msg = Message(
            id="1",
            session_id="s1",
            from_instance="telegram",
            sender=Sender(platform_id="u1", name="User"),
            ts=datetime.now(timezone.utc),
            text="I need help",
            group_id="support-team",
        )
        
        assert rule.match_message(msg) is True
        
        # Different group
        msg.group_id = "random-chat"
        assert rule.match_message(msg) is False
        
        # Different channel
        msg.from_instance = "email"
        msg.group_id = "support-team"
        assert rule.match_message(msg) is False


class TestRoutingEngine:
    """Tests for RoutingEngine."""
    
    @pytest.fixture
    def exchange(self):
        return FakeExchange()
    
    @pytest.fixture
    def config(self):
        return {
            "routing": {
                "enabled": True,
                "default_action": "keep",
                "default_instance": "unprocessed",
                "rules": [
                    {
                        "name": "email_to_telegram",
                        "priority": 100,
                        "match": {
                            "from_channel": "email",
                        },
                        "actions": {
                            "forward_to": ["telegram"],
                            "extensions": [],
                        },
                    },
                    {
                        "name": "support_to_handler",
                        "priority": 50,
                        "match": {
                            "from_channel": "telegram",
                            "group_id_pattern": "support-*",
                        },
                        "actions": {
                            "forward_to": ["handler"],
                            "extensions": [],
                        },
                    },
                ],
            },
        }
    
    def test_engine_initialization(self, exchange, config):
        engine = RoutingEngine(exchange, config)
        
        assert engine._routing_enabled is True
        assert len(engine._rules) == 2
        assert engine._default_action == "keep"
    
    def test_find_matching_rule(self, exchange, config):
        engine = RoutingEngine(exchange, config)
        
        # Email message matches email_to_telegram rule
        msg = Message(
            id="1",
            session_id="s1",
            from_instance="email",
            sender=Sender(platform_id="u1", name="User"),
            ts=datetime.now(timezone.utc),
            text="Hello",
        )
        
        rule = engine.find_matching_rule(msg)
        assert rule is not None
        assert rule.name == "email_to_telegram"
    
    def test_no_matching_rule(self, exchange, config):
        engine = RoutingEngine(exchange, config)
        
        # Web message doesn't match any rule
        msg = Message(
            id="1",
            session_id="s1",
            from_instance="web",
            sender=Sender(platform_id="u1", name="User"),
            ts=datetime.now(timezone.utc),
            text="Hello",
        )
        
        rule = engine.find_matching_rule(msg)
        assert rule is None
    
    def test_default_destination(self, exchange, config):
        engine = RoutingEngine(exchange, config)
        
        destinations = engine.get_default_destination()
        assert destinations == ["unprocessed"]
    
    def test_priority_ordering(self, exchange, config):
        engine = RoutingEngine(exchange, config)
        
        # Rules should be sorted by priority
        priorities = [r.priority for r in engine._rules]
        assert priorities == [50, 100]  # 50 comes before 100


class TestLoadRulesFromConfig:
    """Tests for loading rules from config."""
    
    def test_load_rules(self):
        config = {
            "routing": {
                "rules": [
                    {"name": "rule1", "priority": 100},
                    {"name": "rule2", "priority": 50},
                    {"name": "rule3", "priority": 75},
                ],
            },
        }
        
        rules = load_rules_from_config(config)
        
        assert len(rules) == 3
        assert rules[0].name == "rule2"  # priority 50
        assert rules[1].name == "rule3"  # priority 75
        assert rules[2].name == "rule1"  # priority 100
    
    def test_empty_rules(self):
        rules = load_rules_from_config({})
        assert len(rules) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
