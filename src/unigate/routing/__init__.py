"""Routing module - routes messages based on configurable rules."""

from .engine import RoutingEngine
from .rule import RoutingRule, RoutingAction
from .matcher import RuleMatcher

__all__ = ["RoutingEngine", "RoutingRule", "RoutingAction", "RuleMatcher"]
