"""Source schema."""

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, field_serializer, field_validator

from airweave.platform.auth.schemas import AuthType
from airweave.platform.configs._base import Fields


class SourceBase(BaseModel):
    """Base schema for Source."""

    name: str
    description: Optional[str] = None
    auth_type: Optional[AuthType] = None
    auth_config_class: str
    config_class: str  # Required field
    short_name: str
    class_name: str
    output_entity_definition_ids: Optional[List[UUID]] = None
    organization_id: Optional[UUID] = None
    config_schema: Optional[dict] = None
    labels: Optional[List[str]] = None

    @field_serializer("output_entity_definition_ids")
    def serialize_output_entity_definition_ids(
        self, output_entity_definition_ids: Optional[List[UUID]]
    ) -> Optional[List[str]]:
        """Convert UUID list to string list during serialization."""
        if output_entity_definition_ids is None:
            return None
        return [str(uuid) for uuid in output_entity_definition_ids]

    @field_validator("output_entity_definition_ids", mode="before")
    @classmethod
    def validate_output_entity_definition_ids(cls, value: Any) -> Optional[List[UUID]]:
        """Convert string list to UUID list during deserialization."""
        if value is None:
            return None
        if isinstance(value, list):
            return [UUID(str(item)) if not isinstance(item, UUID) else item for item in value]
        return value

    class Config:
        """Pydantic config for SourceBase."""

        from_attributes = True


class SourceCreate(SourceBase):
    """Schema for creating a Source object."""

    pass


class SourceUpdate(SourceBase):
    """Schema for updating a Source object."""

    pass


class SourceInDBBase(SourceBase):
    """Base schema for Source stored in DB."""

    id: UUID
    created_at: datetime
    modified_at: datetime

    class Config:
        """Pydantic config for SourceInDBBase."""

        from_attributes = True


class Source(SourceInDBBase):
    """Schema for Source."""

    auth_fields: Fields
    config_fields: Optional[Fields] = None  # Not stored in DB, added during API response

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "name": "Stripe",
                    "description": "Connect to Stripe for payment and subscription data",
                    "auth_type": "api_key",
                    "auth_config_class": "StripeAuthConfig",
                    "config_class": "StripeConfig",
                    "short_name": "stripe",
                    "class_name": "StripeSource",
                    "output_entity_definition_ids": ["uuid1", "uuid2"],
                    "organization_id": None,
                    "config_schema": {"type": "object", "properties": {}},
                    "labels": ["payments", "finance"],
                    "created_at": "2024-01-01T00:00:00Z",
                    "modified_at": "2024-01-01T00:00:00Z",
                    "auth_fields": {
                        "fields": [
                            {
                                "name": "api_key",
                                "title": "API Key",
                                "description": (
                                    "The API key for the Stripe account. "
                                    "Should start with 'sk_test_' for test mode "
                                    "or 'sk_live_' for live mode."
                                ),
                                "type": "string",
                            }
                        ]
                    },
                    "config_fields": {"fields": []},
                }
            ]
        }
    }
