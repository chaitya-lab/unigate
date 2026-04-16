"""Storage configuration and factory."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .stores import (
        DedupStore,
        InboxStore,
        InteractionStore,
        OutboxStore,
        SessionStore,
        SecureStore,
    )


@dataclass
class StorageConfig:
    """Storage configuration for an instance or global default."""
    
    backend: str = "memory"  # memory | sqlite | file
    path: str | None = None  # Custom path for sqlite db or file base dir
    
    # SQLite-specific options
    retention_days: int = 7
    dedup_retention_days: int = 1
    
    # File-specific options
    file_retention_days: int = 7
    cleanup_interval_seconds: int = 3600
    
    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "StorageConfig":
        """Create config from dict."""
        if data is None:
            return cls()
        return cls(
            backend=data.get("backend", "memory"),
            path=data.get("path"),
            retention_days=data.get("retention_days", 7),
            dedup_retention_days=data.get("dedup_retention_days", 1),
            file_retention_days=data.get("file_retention_days", 7),
            cleanup_interval_seconds=data.get("cleanup_interval_seconds", 3600),
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "backend": self.backend,
            "path": self.path,
            "retention_days": self.retention_days,
            "dedup_retention_days": self.dedup_retention_days,
            "file_retention_days": self.file_retention_days,
            "cleanup_interval_seconds": self.cleanup_interval_seconds,
        }


class StorageFactory:
    """Factory for creating storage backends."""
    
    _backends: dict[str, type] = {}
    
    @classmethod
    def register_backend(cls, name: str, store_cls: type) -> None:
        """Register a storage backend."""
        cls._backends[name] = store_cls
    
    @classmethod
    def create_stores(
        cls,
        config: StorageConfig,
        namespace: str = "default",
    ) -> tuple[
        "InboxStore",
        "OutboxStore",
        "SessionStore",
        "DedupStore",
        "InteractionStore",
    ]:
        """Create all store instances based on config."""
        backend = config.backend
        
        if backend == "memory":
            from .stores import InMemoryStores
            stores = InMemoryStores()
            return stores, stores, stores, stores, stores
        
        elif backend == "sqlite":
            from .stores import SQLiteStores
            path = config.path or str(Path.home() / ".unigate" / f"{namespace}.db")
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            stores = SQLiteStores(
                path=path,
                retention_days=config.retention_days,
                dedup_retention_days=config.dedup_retention_days,
            )
            return stores, stores, stores, stores, stores
        
        elif backend == "file":
            from .stores import FileStores
            path = config.path or str(Path.home() / ".unigate" / "data" / namespace)
            stores = FileStores(
                base_path=path,
                retention_days=config.file_retention_days,
                cleanup_interval_seconds=config.cleanup_interval_seconds,
            )
            return stores, stores, stores, stores, stores
        
        else:
            # Unknown backend, fall back to memory
            from .stores import InMemoryStores
            stores = InMemoryStores()
            return stores, stores, stores, stores, stores
    
    @classmethod
    def create_secure_store(cls, config: StorageConfig) -> "SecureStore":
        """Create a secure store instance."""
        # SecureStore is always in-memory with encryption support
        from .stores import InMemorySecureStore
        return InMemorySecureStore()


# Register built-in backends
StorageFactory.register_backend("memory", type(None))
StorageFactory.register_backend("sqlite", type(None))
StorageFactory.register_backend("file", type(None))


__all__ = [
    "StorageConfig",
    "StorageFactory",
]
