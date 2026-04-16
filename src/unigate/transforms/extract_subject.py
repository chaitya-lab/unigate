"""Extract subject transform for email-style messages."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..message import Message

from .base import TransformExtension


class ExtractSubjectTransform(TransformExtension):
    """Extract subject from metadata to message text."""

    name = "extract_subject"

    async def transform(self, msg: Message, config: dict[str, Any]) -> Message:
        subject_key = config.get("subject_key", "subject")
        subject = msg.metadata.get(subject_key, "")
        prefix = config.get("prefix", "")
        suffix = config.get("suffix", "")

        original_text = msg.text or ""

        if subject:
            msg.text = f"{prefix}{subject}{suffix}"
            msg.metadata["original_body"] = original_text
        else:
            msg.text = config.get("default_text", "(no subject)")
            msg.metadata["original_body"] = original_text

        return msg


class EmailSubjectOnlyTransform(TransformExtension):
    """Extract email subject, discarding body."""

    name = "email_subject_only"

    async def transform(self, msg: Message, config: dict[str, Any]) -> Message:
        subject = msg.metadata.get("subject", "")
        original_body = msg.text or ""

        if subject:
            msg.text = subject
        else:
            msg.text = "(no subject)"

        msg.metadata["original_body"] = original_body
        msg.metadata["body_preserved"] = True

        return msg
