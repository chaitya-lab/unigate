"""Tests for routing matchers."""

import pytest
from datetime import datetime, timezone

from unigate import Message, Sender, MediaRef, MediaType
from unigate.routing.matchers import get_matcher_registry, MatcherRegistry, RoutingMatcher
from unigate.routing.matchers.channel import ChannelMatcher, ChannelPatternMatcher
from unigate.routing.matchers.sender import (
    SenderMatcher, SenderPatternMatcher, SenderNameMatcher, SenderDomainMatcher
)
from unigate.routing.matchers.text import (
    TextContainsMatcher, TextPatternMatcher, TextStartsWithMatcher, TextCommandMatcher
)
from unigate.routing.matchers.media import (
    HasMediaMatcher, HasAttachmentMatcher, MediaTypeMatcher, HasImageMatcher
)


class TestMatcherRegistry:
    """Test matcher registry."""

    def test_registry_singleton(self):
        registry1 = get_matcher_registry()
        registry2 = get_matcher_registry()
        assert registry1 is registry2

    def test_registry_has_builtins(self):
        registry = get_matcher_registry()
        names = registry.list_names()
        assert "from_channel" in names
        assert "sender_id" in names
        assert "text_contains" in names
        assert "has_media" in names
        assert "day_of_week" in names

    def test_create_matcher(self):
        registry = get_matcher_registry()
        matcher = registry.create("from_channel")
        assert matcher is not None
        assert isinstance(matcher, ChannelMatcher)


class TestChannelMatcher:
    """Test channel matcher."""

    def test_match_exact(self):
        matcher = ChannelMatcher()
        msg = Message(
            id="1",
            session_id="s1",
            from_instance="telegram",
            sender=Sender(platform_id="u1", name="Test"),
            ts=datetime.now(timezone.utc),
        )
        assert matcher.match(msg, "telegram") is True
        assert matcher.match(msg, "whatsapp") is False

    def test_match_list(self):
        matcher = ChannelMatcher()
        msg = Message(
            id="1",
            session_id="s1",
            from_instance="telegram",
            sender=Sender(platform_id="u1", name="Test"),
            ts=datetime.now(timezone.utc),
        )
        assert matcher.match(msg, ["telegram", "whatsapp"]) is True
        assert matcher.match(msg, ["email", "slack"]) is False


class TestSenderMatcher:
    """Test sender matchers."""

    def test_sender_id_exact(self):
        matcher = SenderMatcher()
        msg = Message(
            id="1",
            session_id="s1",
            from_instance="test",
            sender=Sender(platform_id="user123", name="Test User"),
            ts=datetime.now(timezone.utc),
        )
        assert matcher.match(msg, "user123") is True
        assert matcher.match(msg, "other") is False

    def test_sender_pattern_glob(self):
        matcher = SenderPatternMatcher()
        msg = Message(
            id="1",
            session_id="s1",
            from_instance="test",
            sender=Sender(platform_id="user@example.com", name="Test"),
            ts=datetime.now(timezone.utc),
        )
        assert matcher.match(msg, "user@*") is True
        assert matcher.match(msg, "admin@*") is False

    def test_sender_name_contains(self):
        matcher = SenderNameMatcher()
        msg = Message(
            id="1",
            session_id="s1",
            from_instance="test",
            sender=Sender(platform_id="u1", name="John Doe"),
            ts=datetime.now(timezone.utc),
        )
        assert matcher.match(msg, "John") is True
        assert matcher.match(msg, "jane") is False

    def test_sender_domain(self):
        matcher = SenderDomainMatcher()
        msg = Message(
            id="1",
            session_id="s1",
            from_instance="test",
            sender=Sender(platform_id="u1", name="Test", handle="user@company.com"),
            ts=datetime.now(timezone.utc),
        )
        assert matcher.match(msg, "company.com") is True
        assert matcher.match(msg, "other.com") is False


class TestTextMatcher:
    """Test text matchers."""

    def test_text_contains(self):
        matcher = TextContainsMatcher()
        msg = Message(
            id="1",
            session_id="s1",
            from_instance="test",
            sender=Sender(platform_id="u1", name="Test"),
            ts=datetime.now(timezone.utc),
            text="Hello World",
        )
        assert matcher.match(msg, "World") is True
        assert matcher.match(msg, "world") is True
        assert matcher.match(msg, "Foo") is False

    def test_text_pattern_regex(self):
        matcher = TextPatternMatcher()
        msg = Message(
            id="1",
            session_id="s1",
            from_instance="test",
            sender=Sender(platform_id="u1", name="Test"),
            ts=datetime.now(timezone.utc),
            text="Order #12345",
        )
        assert matcher.match(msg, r"Order #\d+") is True
        assert matcher.match(msg, r"Invoice \d+") is False

    def test_text_starts_with(self):
        matcher = TextStartsWithMatcher()
        msg = Message(
            id="1",
            session_id="s1",
            from_instance="test",
            sender=Sender(platform_id="u1", name="Test"),
            ts=datetime.now(timezone.utc),
            text="/start",
        )
        assert matcher.match(msg, "/") is True
        assert matcher.match(msg, "/start") is True
        assert matcher.match(msg, "help") is False

    def test_is_command(self):
        matcher = TextCommandMatcher()
        msg = Message(
            id="1",
            session_id="s1",
            from_instance="test",
            sender=Sender(platform_id="u1", name="Test"),
            ts=datetime.now(timezone.utc),
            text="/help",
        )
        assert matcher.match(msg, True) is True
        assert matcher.match(msg, False) is False


class TestMediaMatcher:
    """Test media matchers."""

    def test_has_media_true(self):
        matcher = HasMediaMatcher()
        msg = Message(
            id="1",
            session_id="s1",
            from_instance="test",
            sender=Sender(platform_id="u1", name="Test"),
            ts=datetime.now(timezone.utc),
            media=[
                MediaRef(media_id="img1", type=MediaType.IMAGE),
            ],
        )
        assert matcher.match(msg, True) is True
        assert matcher.match(msg, False) is False

    def test_has_media_false(self):
        matcher = HasMediaMatcher()
        msg = Message(
            id="1",
            session_id="s1",
            from_instance="test",
            sender=Sender(platform_id="u1", name="Test"),
            ts=datetime.now(timezone.utc),
        )
        assert matcher.match(msg, True) is False
        assert matcher.match(msg, False) is True

    def test_has_attachment(self):
        matcher = HasAttachmentMatcher()
        msg = Message(
            id="1",
            session_id="s1",
            from_instance="test",
            sender=Sender(platform_id="u1", name="Test"),
            ts=datetime.now(timezone.utc),
            media=[
                MediaRef(media_id="doc1", type=MediaType.FILE),
            ],
        )
        assert matcher.match(msg, True) is True

    def test_has_image(self):
        matcher = HasImageMatcher()
        msg = Message(
            id="1",
            session_id="s1",
            from_instance="test",
            sender=Sender(platform_id="u1", name="Test"),
            ts=datetime.now(timezone.utc),
            media=[
                MediaRef(media_id="img1", type=MediaType.IMAGE),
            ],
        )
        assert matcher.match(msg, True) is True

    def test_media_type(self):
        matcher = MediaTypeMatcher()
        msg = Message(
            id="1",
            session_id="s1",
            from_instance="test",
            sender=Sender(platform_id="u1", name="Test"),
            ts=datetime.now(timezone.utc),
            media=[
                MediaRef(media_id="vid1", type=MediaType.VIDEO),
            ],
        )
        assert matcher.match(msg, "video") is True
        assert matcher.match(msg, ["video", "audio"]) is True
        assert matcher.match(msg, "image") is False


class TestTimeMatcher:
    """Test time matchers."""

    def test_day_of_week(self):
        from unigate.routing.matchers.time import DayOfWeekMatcher
        
        matcher = DayOfWeekMatcher()
        msg = Message(
            id="1",
            session_id="s1",
            from_instance="test",
            sender=Sender(platform_id="u1", name="Test"),
            ts=datetime(2024, 1, 8, 12, 0, 0),  # Monday
        )
        assert matcher.match(msg, "monday") is True
        assert matcher.match(msg, ["monday", "tuesday"]) is True
        assert matcher.match(msg, "friday") is False

    def test_hour_of_day(self):
        from unigate.routing.matchers.time import HourOfDayMatcher
        
        matcher = HourOfDayMatcher()
        msg = Message(
            id="1",
            session_id="s1",
            from_instance="test",
            sender=Sender(platform_id="u1", name="Test"),
            ts=datetime(2024, 1, 8, 14, 30, 0),  # 2:30 PM
        )
        assert matcher.match(msg, 14) is True
        assert matcher.match(msg, [9, 10, 11, 12, 13, 14]) is True
        assert matcher.match(msg, "9-17") is True
        assert matcher.match(msg, "18-22") is False
