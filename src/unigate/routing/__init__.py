"""Routing module - routes messages based on configurable rules."""

from .engine import RoutingEngine
from .rule import RoutingRule, RoutingAction, MatchCondition
from .matcher import RuleMatcher

__all__ = [
    "RoutingEngine",
    "RoutingRule",
    "RoutingAction",
    "MatchCondition",
    "RuleMatcher",
]
