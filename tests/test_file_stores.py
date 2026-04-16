"""Tests for file-based storage backend."""

import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from unigate.message import Message, Sender
from unigate.stores import (
    DedupStore,
    FileStores,
    InboxRecord,
    InboxStore,
    InteractionStore,
    OutboxRecord,
    OutboxStore,
    SessionStore,
)


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def stores(temp_dir):
    return FileStores(base_path=f"{temp_dir}/unigate", retention_days=1)


@pytest.fixture
def sample_message():
    sender = Sender(platform_id="test-user", name="Test User")
    return Message(
        id="msg-001",
        session_id="session-001",
        from_instance="test",
        sender=sender,
        ts=datetime.now(timezone.utc),
        text="Hello World",
    )


class TestFileStoresBasics:
    def test_inbox_store(self, stores, sample_message):
        record = InboxRecord(
            message_id=sample_message.id,
            instance_id="test",
            message=sample_message,
            received_at=datetime.now(timezone.utc),
        )
        asyncio.run(stores.put(record))
        
        records = asyncio.run(stores.list_inbox())
        assert len(records) == 1
        assert records[0].message_id == sample_message.id

    def test_outbox_store(self, stores, sample_message):
        record = OutboxRecord(
            outbox_id="out-001",
            instance_id="test",
            destination="test",
            message=sample_message,
            status="pending",
            attempts=0,
        )
        asyncio.run(stores.put_many([record]))
        
        records = asyncio.run(stores.list_outbox())
        assert len(records) == 1
        assert records[0].outbox_id == "out-001"

    def test_due_records(self, stores, sample_message):
        record = OutboxRecord(
            outbox_id="out-due",
            instance_id="test",
            destination="test",
            message=sample_message,
            status="pending",
            attempts=0,
        )
        asyncio.run(stores.put_many([record]))
        
        due = asyncio.run(stores.due(datetime.now(timezone.utc)))
        assert len(due) == 1
        assert due[0].outbox_id == "out-due"

    def test_mark_sent_moves_to_sent_folder(self, stores, temp_dir, sample_message):
        record = OutboxRecord(
            outbox_id="out-sent",
            instance_id="test",
            destination="test",
            message=sample_message,
            status="pending",
            attempts=0,
        )
        asyncio.run(stores.put_many([record]))
        asyncio.run(stores.mark_sent("out-sent"))
        
        # Check outbox is empty
        records = asyncio.run(stores.list_outbox())
        assert len(records) == 0
        
        # Check sent folder has the file
        sent_path = Path(temp_dir) / "unigate" / "sent"
        sent_files = list(sent_path.glob("*.json"))
        assert len(sent_files) == 1

    def test_mark_failed_updates_status(self, stores, sample_message):
        record = OutboxRecord(
            outbox_id="out-fail",
            instance_id="test",
            destination="test",
            message=sample_message,
            status="pending",
            attempts=0,
        )
        asyncio.run(stores.put_many([record]))
        asyncio.run(stores.mark_failed("out-fail", "test error", None))
        
        due = asyncio.run(stores.due(datetime.now(timezone.utc)))
        assert len(due) == 0  # Status changed to failed

    def test_dead_letter(self, stores, sample_message):
        record = OutboxRecord(
            outbox_id="out-dl",
            instance_id="test",
            destination="test",
            message=sample_message,
            status="pending",
            attempts=0,
        )
        asyncio.run(stores.put_many([record]))
        asyncio.run(stores.move_to_dead_letter("out-dl", "max retries"))
        
        records = asyncio.run(stores.list_outbox())
        assert len(records) == 0
        
        dead_letters = asyncio.run(stores.list_dead_letters())
        assert len(dead_letters) == 1
        assert dead_letters[0].outbox_id == "out-dl"

    def test_session_store(self, stores):
        asyncio.run(stores.set_origin("session-123", "telegram"))
        origin = asyncio.run(stores.get_origin("session-123"))
        assert origin == "telegram"

    def test_dedup_store(self, stores):
        asyncio.run(stores.mark("key-001"))
        seen = asyncio.run(stores.seen("key-001"))
        assert seen is True
        
        not_seen = asyncio.run(stores.seen("key-002"))
        assert not_seen is False

    def test_interaction_store(self, stores):
        from unigate.stores import PendingInteractionRecord
        
        record = PendingInteractionRecord(
            interaction_id="int-001",
            session_id="session-001",
            instance_id="test",
            timeout_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        asyncio.run(stores.put_interaction(record))
        
        found = asyncio.run(stores.get_interaction("session-001", "test"))
        assert found is not None
        assert found.interaction_id == "int-001"
        
        asyncio.run(stores.remove_interaction("int-001"))
        found = asyncio.run(stores.get_interaction("session-001", "test"))
        assert found is None


class TestFileStoresDirectoryStructure:
    def test_creates_directory_structure(self, temp_dir):
        stores = FileStores(base_path=f"{temp_dir}/unigate2")
        
        base = Path(temp_dir) / "unigate2"
        assert (base / "inbox").exists()
        assert (base / "outbox").exists()
        assert (base / "sent").exists()
        assert (base / "dead_letters").exists()
        assert (base / "sessions").exists()
        assert (base / "dedup").exists()
        assert (base / "interactions").exists()


class TestFileStoresPersistence:
    def test_data_persists_after_restart(self, temp_dir, sample_message):
        # Create and populate
        stores1 = FileStores(base_path=f"{temp_dir}/unigate3")
        record = OutboxRecord(
            outbox_id="persist-001",
            instance_id="test",
            destination="test",
            message=sample_message,
            status="pending",
            attempts=0,
        )
        asyncio.run(stores1.put_many([record]))
        
        # Create new instance (simulating restart)
        stores2 = FileStores(base_path=f"{temp_dir}/unigate3")
        records = asyncio.run(stores2.list_outbox())
        
        assert len(records) == 1
        assert records[0].outbox_id == "persist-001"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
