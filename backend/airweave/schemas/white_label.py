"""White label schema."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr


class WhiteLabelBase(BaseModel):
    """Base schema for WhiteLabel."""

    name: str
    source_short_name: str
    redirect_url: str
    client_id: str
    client_secret: str
    allowed_origins: str

    class Config:
        """Pydantic config for WhiteLabelBase."""

        from_attributes = True


class WhiteLabelCreate(WhiteLabelBase):
    """Schema for creating a WhiteLabel object."""

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Company Slack Integration",
                    "source_short_name": "slack",
                    "redirect_url": "https://yourapp.com/auth/slack/callback",
                    "client_id": "1234567890.1234567890123",
                    "client_secret": "abcdefghijklmnopqrstuvwxyz123456",
                    "allowed_origins": "https://yourapp.com,https://app.yourapp.com",
                }
            ]
        }
    }


class WhiteLabelUpdate(BaseModel):
    """Schema for updating a WhiteLabel object."""

    name: Optional[str] = None
    redirect_url: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    allowed_origins: Optional[str] = None


class WhiteLabelInDBBase(WhiteLabelBase):
    """Base schema for WhiteLabel stored in DB."""

    id: UUID
    organization_id: UUID
    created_at: datetime
    modified_at: datetime
    created_by_email: EmailStr
    modified_by_email: EmailStr

    class Config:
        """Pydantic config for WhiteLabelInDBBase."""

        from_attributes = True


class WhiteLabel(WhiteLabelInDBBase):
    """Schema for WhiteLabel."""

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": "white123-4567-89ab-cdef-012345678901",
                    "name": "Company Slack Integration",
                    "source_short_name": "slack",
                    "redirect_url": "https://yourapp.com/auth/slack/callback",
                    "client_id": "1234567890.1234567890123",
                    "client_secret": "abcdefghijklmnopqrstuvwxyz123456",
                    "allowed_origins": "https://yourapp.com,https://app.yourapp.com",
                    "organization_id": "org12345-6789-abcd-ef01-234567890abc",
                    "created_at": "2024-01-10T08:15:00Z",
                    "modified_at": "2024-01-15T09:30:00Z",
                    "created_by_email": "admin@company.com",
                    "modified_by_email": "devops@company.com",
                }
            ]
        },
    }
