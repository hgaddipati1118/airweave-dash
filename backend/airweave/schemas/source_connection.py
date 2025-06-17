"""Source connection schemas."""

import re
from datetime import datetime
from typing import Any, Dict, Optional, Tuple, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from airweave.core.shared_models import SourceConnectionStatus, SyncJobStatus
from airweave.platform.configs._base import ConfigValues


class SourceConnectionBase(BaseModel):
    """Base schema for source connection."""

    name: str = Field(..., description="Name of the source connection", min_length=4, max_length=42)
    description: Optional[str] = None
    config_fields: Optional[ConfigValues] = None  # stored in core table
    short_name: str  # Short name of the source
    white_label_id: Optional[UUID] = None  # ID of the white label integration

    class Config:
        """Pydantic config for SourceConnectionBase."""

        from_attributes = True


class SourceConnectionCreate(SourceConnectionBase):
    """Schema for creating a source connection.

    Contains all fields that are required to create a source connection.
    - Sync specific fields are included here.
    """

    collection: Optional[str] = None
    cron_schedule: Optional[str] = None
    auth_fields: Optional[ConfigValues] = None
    credential_id: Optional[UUID] = None
    sync_immediately: bool = True

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "My Stripe Connection",
                    "description": "Production Stripe account for payment data",
                    "short_name": "stripe",
                    "collection": "finance-data",
                    "auth_fields": {"api_key": "sk_live_51H..."},
                    "cron_schedule": "0 */6 * * *",
                    "sync_immediately": True,
                }
            ]
        }
    )

    @field_validator("cron_schedule")
    def validate_cron_schedule(cls, v: str) -> str:
        """Validate cron schedule format.

        Format: * * * * *
        minute (0-59)
        hour (0-23)
        day of month (1-31)
        month (1-12 or JAN-DEC)
        day of week (0-6 or SUN-SAT)

        * * * * *
        │ │ │ │ │
        │ │ │ │ └─ Day of week (0-6 or SUN-SAT)
        │ │ │ └─── Month (1-12 or JAN-DEC)
        │ │ └───── Day of month (1-31)
        │ └─────── Hour (0-23)
        └───────── Minute (0-59)
        """
        if v is None:
            return None
        cron_pattern = r"^(\*|[0-9]{1,2}|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) (\*|[0-9]{1,2}|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) (\*|[0-9]{1,2}|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) (\*|[0-9]{1,2}|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) (\*|[0-6]|SUN|MON|TUE|WED|THU|FRI|SAT|[0-6]-[0-6]|[0-6]/[0-6]|[0-6],[0-6]|\*\/[0-6])$"  # noqa: E501
        if not re.match(cron_pattern, v):
            raise ValueError("Invalid cron schedule format")
        return v

    def map_to_core_and_auxiliary_attributes(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Map the source connection create schema to core and auxiliary attributes.

        This separates the attributes in the schema into two groups:
        1. Core attributes: These are used to create the SourceConnection model directly
        2. Auxiliary attributes: These are used in the creation process but aren't part of the model

        Returns:
            A tuple containing (core_attributes, auxiliary_attributes)
        """
        data = self.model_dump(exclude_unset=True)

        # Auxiliary attributes used in the creation process but not directly in the model
        auxiliary_attrs = {
            "auth_fields": data.pop("auth_fields", None),
            "credential_id": data.pop("credential_id", None),
            "cron_schedule": data.pop("cron_schedule", None),
            "sync_immediately": data.pop("sync_immediately", True),
        }

        # Everything else is a core attribute for the SourceConnection model
        core_attrs = data

        return core_attrs, auxiliary_attrs


class SourceConnectionUpdate(BaseModel):
    """Schema for updating a source connection."""

    name: Optional[str] = Field(
        None, description="Name of the source connection", min_length=4, max_length=42
    )
    description: Optional[str] = None
    auth_fields: Optional[Union[ConfigValues, str]] = None
    config_fields: Optional[ConfigValues] = None
    cron_schedule: Optional[str] = None
    connection_id: Optional[UUID] = None
    white_label_id: Optional[UUID] = None


class SourceConnectionInDBBase(SourceConnectionBase):
    """Core schema for source connection stored in DB."""

    id: UUID
    sync_id: Optional[UUID] = None
    organization_id: UUID
    created_at: datetime
    modified_at: datetime
    connection_id: Optional[UUID] = None  # ID of the underlying connection object
    collection: str
    white_label_id: Optional[UUID] = None
    created_by_email: EmailStr
    modified_by_email: EmailStr

    class Config:
        """Pydantic config for SourceConnectionInDBBase."""

        from_attributes = True


class SourceConnection(SourceConnectionInDBBase):
    """Schema for source connection."""

    # str if encrypted/masked, ConfigValues if not
    # comes from integration_credential
    auth_fields: Optional[Union[ConfigValues, str]] = None

    # Ephemeral status derived from the latest sync job
    status: Optional[SourceConnectionStatus] = None

    # sync job info
    latest_sync_job_status: Optional[SyncJobStatus] = None
    latest_sync_job_id: Optional[UUID] = None
    latest_sync_job_started_at: Optional[datetime] = None
    latest_sync_job_completed_at: Optional[datetime] = None
    latest_sync_job_error: Optional[str] = None

    # Sync schedule information
    cron_schedule: Optional[str] = None
    next_scheduled_run: Optional[datetime] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "name": "My Stripe Connection",
                    "description": "Production Stripe account for payment data",
                    "short_name": "stripe",
                    "collection": "finance-data",
                    "status": "active",
                    "sync_id": "123e4567-e89b-12d3-a456-426614174000",
                    "organization_id": "org12345-6789-abcd-ef01-234567890abc",
                    "connection_id": "conn9876-5432-10fe-dcba-098765432100",
                    "white_label_id": None,
                    "created_at": "2024-01-15T09:30:00Z",
                    "modified_at": "2024-01-15T14:22:15Z",
                    "created_by_email": "finance@company.com",
                    "modified_by_email": "finance@company.com",
                    "auth_fields": {"api_key": "sk_live_51H..."},
                    "config_fields": {},
                    "latest_sync_job_status": "completed",
                    "latest_sync_job_id": "987fcdeb-51a2-43d7-8f3e-1234567890ab",
                    "latest_sync_job_started_at": "2024-01-15T14:00:00Z",
                    "latest_sync_job_completed_at": "2024-01-15T14:05:22Z",
                    "latest_sync_job_error": None,
                    "cron_schedule": "0 */6 * * *",
                    "next_scheduled_run": "2024-01-16T02:00:00Z",
                }
            ]
        },
    )

    @classmethod
    def from_orm_with_collection_mapping(cls, obj):
        """Create a SourceConnection from a source_connection ORM model."""
        # Convert to dict and filter out SQLAlchemy internal attributes
        obj_dict = {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}

        # Map the readable_collection_id to collection if needed
        if hasattr(obj, "readable_collection_id"):
            obj_dict["collection"] = obj.readable_collection_id

        return cls.model_validate(obj_dict)


class SourceConnectionListItem(BaseModel):
    """Simplified schema for source connection list item.

    This is a compact representation containing only core attributes
    directly from the source connection model.
    """

    id: UUID
    name: str
    description: Optional[str] = None
    short_name: str
    status: SourceConnectionStatus
    created_at: datetime
    modified_at: datetime
    sync_id: UUID
    collection: str
    white_label_id: Optional[UUID] = None

    @model_validator(mode="after")
    def map_collection_readable_id(self) -> "SourceConnectionListItem":
        """Map collection_readable_id to collection if present."""
        # This is handled in the before mode validator below
        return self

    @model_validator(mode="before")
    @classmethod
    def map_collection_field(cls, data: Any) -> Any:
        """Map collection_readable_id to collection before validation."""
        if isinstance(data, dict):
            # If collection_readable_id exists and collection doesn't, map it
            if "collection_readable_id" in data and "collection" not in data:
                data["collection"] = data["collection_readable_id"]
        elif hasattr(data, "readable_collection_id"):
            # If it's an ORM object, we need to convert to dict first
            # Extract all attributes we need
            data_dict = {}
            for field in cls.model_fields:
                if hasattr(data, field):
                    data_dict[field] = getattr(data, field)

            data_dict["collection"] = data.readable_collection_id

            return data_dict
        return data

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "name": "My Stripe Connection",
                    "description": "Production Stripe account for payment data",
                    "short_name": "stripe",
                    "status": "active",
                    "created_at": "2024-01-15T09:30:00Z",
                    "modified_at": "2024-01-15T14:22:15Z",
                    "sync_id": "123e4567-e89b-12d3-a456-426614174000",
                    "collection": "finance-data-x236",
                    "white_label_id": None,
                }
            ]
        },
    )
