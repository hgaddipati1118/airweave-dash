"""Notion entity schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from airweave.platform.entities._base import ChunkEntity, FileEntity
from airweave.platform.entities._lazy import LazyEntity


class NotionDatabaseEntity(ChunkEntity):
    """Schema for a Notion database."""

    database_id: str = Field(..., description="The ID of the database")
    title: str = Field(..., description="The title of the database")
    description: str = Field(default="", description="The description of the database")
    properties: Dict[str, Any] = Field(
        default_factory=dict, description="Database properties schema"
    )
    parent_id: str = Field(description="The ID of the parent")
    parent_type: str = Field(description="The type of the parent (workspace, page_id, etc.)")
    icon: Optional[Dict[str, Any]] = Field(None, description="The icon of the database")
    cover: Optional[Dict[str, Any]] = Field(None, description="The cover of the database")
    archived: bool = Field(default=False, description="Whether the database is archived")
    is_inline: bool = Field(default=False, description="Whether the database is inline")
    url: str = Field(description="The URL of the database")
    created_time: Optional[datetime] = Field(None, description="When the database was created")
    last_edited_time: Optional[datetime] = Field(
        None, description="When the database was last edited"
    )


class NotionPageEntity(ChunkEntity, LazyEntity):
    """Schema for a Notion page with aggregated content."""

    page_id: str = Field(..., description="The ID of the page")
    parent_id: str = Field(description="The ID of the parent")
    parent_type: str = Field(
        description="The type of the parent (workspace, page_id, database_id, etc.)"
    )
    title: str = Field(..., description="The title of the page")
    content: Optional[str] = Field(default=None, description="Full aggregated content")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Page properties")
    property_entities: List[Any] = Field(
        default_factory=list, description="Structured property entities"
    )
    files: List[Any] = Field(default_factory=list, description="Files referenced in the page")
    icon: Optional[Dict[str, Any]] = Field(None, description="The icon of the page")
    cover: Optional[Dict[str, Any]] = Field(None, description="The cover of the page")
    archived: bool = Field(default=False, description="Whether the page is archived")
    in_trash: bool = Field(default=False, description="Whether the page is in trash")
    url: str = Field(description="The URL of the page")
    content_blocks_count: int = Field(default=0, description="Number of blocks processed")
    max_depth: int = Field(default=0, description="Maximum nesting depth of blocks")
    created_time: Optional[datetime] = Field(None, description="When the page was created")
    last_edited_time: Optional[datetime] = Field(None, description="When the page was last edited")

    def __init__(self, **data):
        """Initialize NotionPageEntity ensuring LazyEntity setup."""
        super().__init__(**data)
        # Ensure LazyEntity initialization
        if not hasattr(self, "_lazy_operations"):
            self._lazy_operations = {}
        if not hasattr(self, "_lazy_results"):
            self._lazy_results = {}
        if not hasattr(self, "_is_materialized"):
            self._is_materialized = False

    async def _apply_results(self) -> None:
        """Apply lazy operation results to entity fields."""
        if "aggregate_content" in self._lazy_results:
            result = self._lazy_results["aggregate_content"]
            self.content = result.get("content", "")
            self.content_blocks_count = result.get("blocks_count", 0)
            self.max_depth = result.get("max_depth", 0)
            # Don't populate files - they should be yielded separately,
            # not included in the page entity
            # self.files = result.get('files', [])

        if "extract_properties" in self._lazy_results:
            self.property_entities = self._lazy_results["extract_properties"]


class NotionPropertyEntity(ChunkEntity):
    """Schema for a Notion database page property."""

    property_id: str = Field(..., description="The ID of the property")
    property_name: str = Field(..., description="The name of the property")
    property_type: str = Field(..., description="The type of the property")
    page_id: str = Field(..., description="The ID of the page this property belongs to")
    database_id: str = Field(..., description="The ID of the database this property belongs to")
    value: Optional[Any] = Field(None, description="The raw value of the property")
    formatted_value: str = Field(
        default="", description="The formatted/display value of the property"
    )


class NotionFileEntity(FileEntity):
    """Schema for a Notion file."""

    # Notion-specific fields
    file_type: str = Field(..., description="The type of file (file, external, file_upload)")
    url: str = Field(..., description="The URL to access the file")
    expiry_time: Optional[datetime] = Field(
        None, description="When the file URL expires (for Notion-hosted files)"
    )
    caption: str = Field(default="", description="The caption of the file")

    # Initialize metadata field to ensure it exists
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional metadata about the file"
    )

    def needs_refresh(self) -> bool:
        """Check if the file URL needs to be refreshed (for Notion-hosted files)."""
        if self.file_type == "file" and self.expiry_time:
            from datetime import datetime, timezone

            return datetime.now(timezone.utc) >= self.expiry_time
        return False

    def hash(self) -> str:
        """Hash the file entity.

        For files, we try the following strategies in order:
        1. If local_path is available, compute hash from actual file contents
        2. If checksum is available, use it as part of metadata hash
        3. Fall back to parent hash method using all metadata
        """
        if getattr(self, "_hash", None):
            return self._hash

        if hasattr(self, "local_path") and self.local_path:
            # If we have the actual file, compute hash from its contents
            try:
                import hashlib

                with open(self.local_path, "rb") as f:
                    content = f.read()
                    self._hash = hashlib.sha256(content).hexdigest()
                    return self._hash
            except Exception:
                # If file read fails, fall through to next method
                pass

        # Fall back to parent hash method
        return super().hash()
