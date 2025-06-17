"""Entity model."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import OrganizationBase

if TYPE_CHECKING:
    from airweave.models.sync import Sync
    from airweave.models.sync_job import SyncJob


class Entity(OrganizationBase):
    """Entity model."""

    __tablename__ = "entity"

    sync_job_id: Mapped[UUID] = mapped_column(
        ForeignKey("sync_job.id", ondelete="CASCADE", name="fk_entity_sync_job_id"), nullable=False
    )
    sync_id: Mapped[UUID] = mapped_column(
        ForeignKey("sync.id", ondelete="CASCADE", name="fk_entity_sync_id"), nullable=False
    )
    entity_id: Mapped[str] = mapped_column(String, nullable=False)
    hash: Mapped[str] = mapped_column(String, nullable=False)

    # Add back references
    sync_job: Mapped["SyncJob"] = relationship(
        "SyncJob",
        back_populates="entities",
        lazy="noload",
    )

    sync: Mapped["Sync"] = relationship(
        "Sync",
        back_populates="entities",
        lazy="noload",
    )

    __table_args__ = (
        UniqueConstraint(
            "sync_id",
            "entity_id",
            name="uq_sync_id_entity_id",
        ),
        # Performance indexes based on common query patterns
        Index("idx_entity_sync_id", "sync_id"),
        Index("idx_entity_sync_job_id", "sync_job_id"),
        Index("idx_entity_entity_id", "entity_id"),
        # Composite index for the most common lookup pattern
        Index("idx_entity_entity_id_sync_id", "entity_id", "sync_id"),
    )
