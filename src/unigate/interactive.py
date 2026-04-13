"""Interactive messaging contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class InteractionType:
    """Built-in interaction type constants.

    Adapters and applications may use additional string values.
    """

    CONFIRM = "confirm"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    TEXT_INPUT = "text_input"
    PASSWORD = "password"
    NUMBER = "number"
    FILE_UPLOAD = "file_upload"
    OTP = "otp"
    FORM = "form"


@dataclass(slots=True)
class FormField:
    """One field inside a structured interaction form."""

    name: str
    label: str
    type: str
    required: bool = True
    options: list[str] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class InteractiveResponse:
    """Normalized response payload for an earlier interactive prompt."""

    interaction_id: str
    type: str
    value: str | list[str] | dict[str, Any] | None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class InteractivePayload:
    """Transport-neutral interactive prompt or response container."""

    interaction_id: str
    type: str
    prompt: str
    options: list[str] | None = None
    fields: list[FormField] | None = None
    min_value: float | None = None
    max_value: float | None = None
    timeout_seconds: int | None = None
    context: dict[str, Any] = field(default_factory=dict)
    response: InteractiveResponse | None = None
