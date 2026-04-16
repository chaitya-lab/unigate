"""Tests for transform plugins."""

import pytest
from datetime import datetime, timezone

from unigate import Message, Sender
from unigate.transforms import (
    TransformExtension,
    TransformRegistry,
    get_transform_registry,
    TruncateTransform,
    ExtractSubjectTransform,
    AddMetadataTransform,
    AddTimestampTransform,
)


class TestTransformRegistry:
    """Test transform registry."""

    def test_registry_singleton(self):
        registry1 = get_transform_registry()
        registry2 = get_transform_registry()
        assert registry1 is registry2

    def test_registry_has_builtins(self):
        registry = get_transform_registry()
        names = registry.list_names()
        assert "truncate" in names
        assert "extract_subject" in names
        assert "add_metadata" in names

    def test_create_transform(self):
        registry = get_transform_registry()
        transform = registry.create("truncate")
        assert transform is not None
        assert isinstance(transform, TruncateTransform)


class TestTruncateTransform:
    """Test truncate transform."""

    @pytest.mark.asyncio
    async def test_truncate_short_text(self):
        transform = TruncateTransform()
        msg = Message(
            id="1",
            session_id="s1",
            from_instance="test",
            sender=Sender(platform_id="u1", name="Test"),
            ts=datetime.now(timezone.utc),
            text="Short text",
        )
        result = await transform.transform(msg, {"max_length": 160})
        assert result.text == "Short text"

    @pytest.mark.asyncio
    async def test_truncate_long_text(self):
        transform = TruncateTransform()
        msg = Message(
            id="1",
            session_id="s1",
            from_instance="test",
            sender=Sender(platform_id="u1", name="Test"),
            ts=datetime.now(timezone.utc),
            text="A" * 200,
        )
        result = await transform.transform(msg, {"max_length": 50, "suffix": "..."})
        assert len(result.text) == 50
        assert result.text.endswith("...")


class TestExtractSubjectTransform:
    """Test extract subject transform."""

    @pytest.mark.asyncio
    async def test_extract_subject(self):
        transform = ExtractSubjectTransform()
        msg = Message(
            id="1",
            session_id="s1",
            from_instance="email",
            sender=Sender(platform_id="u1", name="Test"),
            ts=datetime.now(timezone.utc),
            text="This is the body",
            metadata={"subject": "Test Subject"},
        )
        result = await transform.transform(msg, {})
        assert result.text == "Test Subject"
        assert result.metadata["original_body"] == "This is the body"

    @pytest.mark.asyncio
    async def test_extract_subject_with_prefix(self):
        transform = ExtractSubjectTransform()
        msg = Message(
            id="1",
            session_id="s1",
            from_instance="email",
            sender=Sender(platform_id="u1", name="Test"),
            ts=datetime.now(timezone.utc),
            text="Body text",
            metadata={"subject": "Important"},
        )
        result = await transform.transform(msg, {"prefix": "[Email] "})
        assert result.text == "[Email] Important"


class TestAddMetadataTransform:
    """Test add metadata transform."""

    @pytest.mark.asyncio
    async def test_add_metadata(self):
        transform = AddMetadataTransform()
        msg = Message(
            id="1",
            session_id="s1",
            from_instance="test",
            sender=Sender(platform_id="u1", name="Test"),
            ts=datetime.now(timezone.utc),
            text="Test",
        )
        result = await transform.transform(
            msg, {"metadata": {"tag": "important", "priority": "high"}}
        )
        assert result.metadata["tag"] == "important"
        assert result.metadata["priority"] == "high"


class TestAddTimestampTransform:
    """Test add timestamp transform."""

    @pytest.mark.asyncio
    async def test_add_timestamp_iso(self):
        transform = AddTimestampTransform()
        msg = Message(
            id="1",
            session_id="s1",
            from_instance="test",
            sender=Sender(platform_id="u1", name="Test"),
            ts=datetime.now(timezone.utc),
            text="Test",
        )
        result = await transform.transform(msg, {"key": "routed_at", "format": "iso"})
        assert "routed_at" in result.metadata
        assert "T" in result.metadata["routed_at"]
