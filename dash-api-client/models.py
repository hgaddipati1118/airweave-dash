"""Pydantic models for the Airweave Client API."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import UUID
from pydantic import BaseModel, Field, model_validator
from enum import Enum
import logging


logger = logging.getLogger(__name__)


class SourceType(str, Enum):
    """Source types supported by Airweave."""
    GITHUB = "github"
    NOTION = "notion"
    SLACK = "slack"
    GOOGLE_DRIVE = "google_drive"
    GOOGLE_CALENDAR = "google_calendar"
    GMAIL = "gmail"
    CONFLUENCE = "confluence"
    JIRA = "jira"
    LINEAR = "linear"
    HUBSPOT = "hubspot"
    ASANA = "asana"
    CLICKUP = "clickup"
    DROPBOX = "dropbox"
    ELASTICSEARCH = "elasticsearch"
    INTERCOM = "intercom"
    MONDAY = "monday"
    MYSQL = "mysql"
    ONEDRIVE = "onedrive"
    ORACLE = "oracle"
    OUTLOOK_CALENDAR = "outlook_calendar"
    OUTLOOK_MAIL = "outlook_mail"
    POSTGRESQL = "postgresql"
    SQL_SERVER = "sql_server"
    SQLITE = "sqlite"
    STRIPE = "stripe"
    TODOIST = "todoist"
    TRELLO = "trello"
    ZENDESK = "zendesk"


# Dataclass models for API responses
@dataclass
class AppUser:
    """Application user model."""

    user_id: str
    email: str
    name: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Collection:
    """Collection model."""

    id: UUID
    name: str
    readable_id: str
    organization_id: UUID
    created_at: datetime
    modified_at: datetime
    created_by_email: str
    modified_by_email: str


@dataclass
class Connection:
    """Connection model."""

    id: UUID
    name: str
    short_name: str
    integration_type: str
    organization_id: UUID
    created_at: datetime
    modified_at: datetime
    created_by_email: str
    modified_by_email: str


@dataclass
class SourceConnection:
    """Source connection model."""

    id: UUID
    name: str
    description: Optional[str]
    short_name: str
    config_fields: Optional[Dict[str, Any]]
    sync_id: Optional[UUID]
    readable_collection_id: Optional[UUID]
    connection_id: Optional[UUID]
    white_label_id: Optional[UUID]
    organization_id: UUID
    created_at: datetime
    modified_at: datetime
    created_by_email: str
    modified_by_email: str


@dataclass
class SearchResult:
    """Search result model."""

    id: str
    score: float
    metadata: Dict[str, Any]
    content: str


@dataclass
class SyncJob:
    """Sync job model."""

    id: UUID
    connection_id: UUID
    status: str
    created_at: datetime
    modified_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    failed_at: Optional[datetime]
    error: Optional[str]


# Pydantic models for client configuration
class AirweaveConfig(BaseModel):
    """Configuration for the Airweave client."""
    base_url: str
    timeout: int = 60  # Increased from 30 to 60 seconds


class ConnectionConfig(BaseModel):
    """Connection configuration model."""
    name: str
    source_type: SourceType
    collection_id: str
    auth_fields: Dict[str, Any]
    config_fields: Optional[Dict[str, Any]] = None


# Client-specific Pydantic models (used by AirweaveClient)
class ClientCollection(BaseModel):
    """Client collection model."""
    id: str
    readable_id: str
    name: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None


class ClientConnection(BaseModel):
    """Client connection model."""
    id: str
    name: str
    short_name: str
    collection_id: str
    status: str
    created_at: Optional[datetime] = None


class ClientSyncJob(BaseModel):
    """Client sync job model."""
    id: str
    connection_id: str
    status: str
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class ClientSearchResult(BaseModel):
    """Client search result model."""
    query: str
    results: List[Dict[str, Any]]
    total_results: int
    collection: Optional[str] = None


# Request Models
class CreateCollectionRequest(BaseModel):
    """Request model for creating a collection."""
    name: str = Field(..., description="Collection name")
    description: Optional[str] = Field(None, description="Collection description")
    id: Optional[str] = Field(None, description="Custom collection ID")


class CreateConnectionRequest(BaseModel):
    """Request model for creating a connection."""
    name: str = Field(..., description="Connection name", max_length=42)
    source_type: SourceType = Field(..., description="Type of source to connect to")
    collection_id: str = Field(..., description="Collection ID to sync data to")
    config: Dict[str, Any] = Field(..., description="Connection configuration")

    @model_validator(mode='before')
    @classmethod
    def validate_name(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and transform the name field."""
        if isinstance(data, dict) and 'name' in data and isinstance(data['name'], str):
            if len(data['name']) > 42:
                logger.warning(f"Connection name '{data['name']}' truncated to 42 characters")
                data['name'] = data['name'][:42]
        return data


class SearchRequest(BaseModel):
    """Request model for search operations."""
    query: str = Field(..., description="Search query")
    collection_id: str = Field(..., description="Collection ID to search within")
    limit: int = Field(10, ge=1, le=100, description="Maximum number of results")


class TriggerSyncRequest(BaseModel):
    """Request model for triggering a sync."""
    connection_id: str = Field(..., description="Connection ID to sync")


# Response Models
class CollectionResponse(BaseModel):
    """Response model for collection operations."""
    id: str
    readable_id: str
    name: str
    description: Optional[str] = None
    created_at: Optional[str] = None


class ConnectionResponse(BaseModel):
    """Response model for connection operations."""
    id: str
    name: str
    source_type: str
    collection_name: str
    status: str
    created_at: Optional[str] = None


class SyncResponse(BaseModel):
    """Response model for sync operations."""
    sync_id: str
    connection_id: str
    status: str
    started_at: Optional[str] = None


class SyncStatusResponse(BaseModel):
    """Response model for sync status."""
    sync_id: str
    connection_id: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None


class LatestSyncResponse(BaseModel):
    """Response model for latest sync status."""
    id: str
    sync_id: str
    connection_id: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    modified_at: Optional[str] = None


class SearchResponse(BaseModel):
    """Response model for search operations."""
    query: str
    results: List[Dict[str, Any]]
    total_results: int
    collection: Optional[str] = None
    connections: Optional[List[Dict[str, Any]]] = None 