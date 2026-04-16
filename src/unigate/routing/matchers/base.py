"""Base class and registry for routing matchers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from ...message import Message


class RoutingMatcher(Protocol):
    """Protocol for routing condition matchers."""

    name: str

    def match(self, msg: Message, value: Any) -> bool:
        """Check if message matches condition. Return True if matched."""
        ...


class MatcherRegistry:
    """Registry for routing matchers."""

    def __init__(self) -> None:
        self._matchers: dict[str, type[RoutingMatcher]] = {}

    def register(self, cls: type[RoutingMatcher]) -> None:
        """Register a matcher class."""
        name = getattr(cls, "name", None)
        if name:
            self._matchers[name] = cls

    def get(self, name: str) -> type[RoutingMatcher] | None:
        """Get a matcher class by name."""
        return self._matchers.get(name)

    def create(self, name: str) -> RoutingMatcher | None:
        """Create a matcher instance by name."""
        cls = self.get(name)
        if cls is None:
            return None
        try:
            return cls()
        except Exception:
            return None

    def list_names(self) -> list[str]:
        """List all registered matcher names."""
        return list(self._matchers.keys())


_global_registry: MatcherRegistry | None = None


def get_matcher_registry() -> MatcherRegistry:
    """Get the global matcher registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = MatcherRegistry()
        from .channel import ChannelMatcher, ChannelPatternMatcher
        from .sender import SenderMatcher, SenderPatternMatcher, SenderNameMatcher, SenderDomainMatcher
        from .text import TextContainsMatcher, TextPatternMatcher, TextStartsWithMatcher, TextCommandMatcher
        from .subject import SubjectContainsMatcher, SubjectPatternMatcher, HasSubjectMatcher
        from .context import GroupMatcher, GroupPatternMatcher, ThreadMatcher, SessionMatcher, BotMentionedMatcher
        from .media import HasMediaMatcher, HasAttachmentMatcher, MediaTypeMatcher, HasImageMatcher, HasVideoMatcher
        from .time import DayOfWeekMatcher, HourOfDayMatcher, TimeRangeMatcher
        
        _global_registry.register(ChannelMatcher)
        _global_registry.register(ChannelPatternMatcher)
        _global_registry.register(SenderMatcher)
        _global_registry.register(SenderPatternMatcher)
        _global_registry.register(SenderNameMatcher)
        _global_registry.register(SenderDomainMatcher)
        _global_registry.register(TextContainsMatcher)
        _global_registry.register(TextPatternMatcher)
        _global_registry.register(TextStartsWithMatcher)
        _global_registry.register(TextCommandMatcher)
        _global_registry.register(SubjectContainsMatcher)
        _global_registry.register(SubjectPatternMatcher)
        _global_registry.register(HasSubjectMatcher)
        _global_registry.register(GroupMatcher)
        _global_registry.register(GroupPatternMatcher)
        _global_registry.register(ThreadMatcher)
        _global_registry.register(SessionMatcher)
        _global_registry.register(BotMentionedMatcher)
        _global_registry.register(HasMediaMatcher)
        _global_registry.register(HasAttachmentMatcher)
        _global_registry.register(MediaTypeMatcher)
        _global_registry.register(HasImageMatcher)
        _global_registry.register(HasVideoMatcher)
        _global_registry.register(DayOfWeekMatcher)
        _global_registry.register(HourOfDayMatcher)
        _global_registry.register(TimeRangeMatcher)
    return _global_registry
