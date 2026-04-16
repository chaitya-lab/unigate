"""Extract transform plugins."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..message import Message


class ExtractSubjectTransform:
    """Extract subject from metadata to message text."""
    
    name = "extract_subject"
    type = "transform"
    
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


class EmailSubjectOnlyTransform:
    """Extract email subject, discard body."""
    
    name = "email_subject"
    type = "transform"
    
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


class ExtractPatternTransform:
    """Extract pattern match to metadata."""
    
    name = "extract_pattern"
    type = "transform"
    
    async def transform(self, msg: Message, config: dict[str, Any]) -> Message:
        import re
        
        pattern = config.get("pattern")
        group = config.get("group", 0)
        metadata_key = config.get("metadata_key", "extracted")
        
        if pattern and msg.text:
            try:
                match = re.search(pattern, msg.text)
                if match:
                    msg.metadata[metadata_key] = match.group(group)
            except re.error:
                pass
        
        return msg
