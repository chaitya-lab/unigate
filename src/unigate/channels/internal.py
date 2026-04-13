"""Simple in-process channel implementation."""

from __future__ import annotations

from .loopback import LoopbackChannel


class InternalChannel(LoopbackChannel):
    """In-process channel for embedded application flows."""

    channel_type = "internal"
