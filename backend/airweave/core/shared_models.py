"""Shared models for the backend."""

from enum import Enum


class ConnectionStatus(str, Enum):
    """Connection status enum."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class SyncJobStatus(str, Enum):
    """Sync job status enum."""

    CREATED = "created"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IntegrationType(str, Enum):
    """Integration type enum."""

    SOURCE = "source"
    DESTINATION = "destination"
    EMBEDDING_MODEL = "embedding_model"


class SyncStatus(str, Enum):
    """Sync status enum."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class ChatStatus(str, Enum):
    """Chat status enumeration."""

    ACTIVE = "active"
    ARCHIVED = "archived"


class ChatRole(str, Enum):
    """Role of the message sender."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class SourceConnectionStatus(str, Enum):
    """Source connection status enum."""

    ACTIVE = "active"
    IN_PROGRESS = "in_progress"
    FAILING = "failing"


class CollectionStatus(str, Enum):
    """Collection status enum."""

    ACTIVE = "ACTIVE"
    PARTIAL_ERROR = "PARTIAL ERROR"
    NEEDS_SOURCE = "NEEDS SOURCE"
    ERROR = "ERROR"
