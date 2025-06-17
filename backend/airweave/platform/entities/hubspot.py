"""HubSpot entity schemas.

Based on the HubSpot CRM API reference, we define entity schemas for common
HubSpot objects like Contacts, Companies, Deals, and Tickets.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import Field, field_validator

from airweave.platform.entities._base import ChunkEntity


def parse_hubspot_datetime(value: Any) -> Optional[datetime]:
    """Parse HubSpot datetime value, handling empty strings and various formats.

    Args:
        value: The datetime value from HubSpot API (could be string, datetime, or None)

    Returns:
        Parsed datetime object or None if empty/invalid
    """
    if not value or value == "":
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        try:
            # HubSpot typically returns ISO format datetime strings
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    return None


class HubspotContactEntity(ChunkEntity):
    """Schema for HubSpot contact entities with flexible property handling."""

    # Core fields that are commonly used
    first_name: Optional[str] = Field(default=None, description="The contact's first name")
    last_name: Optional[str] = Field(default=None, description="The contact's last name")
    email: Optional[str] = Field(default=None, description="The contact's email address")

    # All properties from HubSpot API
    properties: Dict[str, Any] = Field(
        default_factory=dict, description="All properties from HubSpot contact object"
    )

    created_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the contact was created"
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the contact was last updated"
    )
    archived: bool = Field(default=False, description="Whether the contact is archived")

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def parse_datetime_fields(cls, v):
        """Parse datetime fields."""
        return parse_hubspot_datetime(v)


class HubspotCompanyEntity(ChunkEntity):
    """Schema for HubSpot company entities with flexible property handling."""

    # Core fields that are commonly used
    name: Optional[str] = Field(default=None, description="The company's name")
    domain: Optional[str] = Field(default=None, description="The company's domain name")

    # All properties from HubSpot API
    properties: Dict[str, Any] = Field(
        default_factory=dict, description="All properties from HubSpot company object"
    )

    created_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the company was created"
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the company was last updated"
    )
    archived: bool = Field(default=False, description="Whether the company is archived")

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def parse_datetime_fields(cls, v):
        """Parse datetime fields."""
        return parse_hubspot_datetime(v)


class HubspotDealEntity(ChunkEntity):
    """Schema for HubSpot deal entities with flexible property handling."""

    # Core fields that are commonly used
    deal_name: Optional[str] = Field(default=None, description="The name of the deal")
    amount: Optional[float] = Field(default=None, description="The monetary value of the deal")

    # All properties from HubSpot API
    properties: Dict[str, Any] = Field(
        default_factory=dict, description="All properties from HubSpot deal object"
    )

    created_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the deal was created"
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the deal was last updated"
    )
    archived: bool = Field(default=False, description="Whether the deal is archived")

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def parse_datetime_fields(cls, v):
        """Parse datetime fields."""
        return parse_hubspot_datetime(v)


class HubspotTicketEntity(ChunkEntity):
    """Schema for HubSpot ticket entities with flexible property handling."""

    # Core fields that are commonly used
    subject: Optional[str] = Field(default=None, description="The subject of the support ticket")
    content: Optional[str] = Field(
        default=None, description="The content or description of the ticket"
    )

    # All properties from HubSpot API
    properties: Dict[str, Any] = Field(
        default_factory=dict, description="All properties from HubSpot ticket object"
    )

    created_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the ticket was created"
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the ticket was last updated"
    )
    archived: bool = Field(default=False, description="Whether the ticket is archived")

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def parse_datetime_fields(cls, v):
        """Parse datetime fields."""
        return parse_hubspot_datetime(v)
