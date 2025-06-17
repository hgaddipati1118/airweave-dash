"""Service for managing sync job status."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from airweave import crud, schemas
from airweave.core.logging import logger
from airweave.core.shared_models import SyncJobStatus
from airweave.db.session import get_db_context
from airweave.platform.sync.pubsub import SyncProgressUpdate


def map_python_enum_to_database(status: SyncJobStatus) -> str:
    """Map Python enum status to database enum value.

    Python enum uses lowercase: pending, in_progress, completed, failed, cancelled
    Database enum uses uppercase: PENDING, IN_PROGRESS, COMPLETED, FAILED, CANCELLED

    Args:
        status: The SyncJobStatus enum value

    Returns:
        The corresponding uppercase database enum string value
    """
    return status.value.upper()


class SyncJobService:
    """Service for managing sync job status updates."""

    def _build_stats_update_data(self, stats: SyncProgressUpdate) -> Dict[str, Any]:
        """Build update data from stats."""
        update_data = {
            "entities_inserted": stats.inserted,
            "entities_updated": stats.updated,
            "entities_deleted": stats.deleted,
            "entities_kept": stats.kept,
            "entities_skipped": stats.skipped,
        }

        # Use the counts directly - they're already in the right format
        if hasattr(stats, "entities_encountered"):
            update_data["entities_encountered"] = stats.entities_encountered

        return update_data

    def _build_timestamp_update_data(
        self,
        status: SyncJobStatus,
        started_at: Optional[datetime],
        completed_at: Optional[datetime],
        failed_at: Optional[datetime],
        error: Optional[str],
    ) -> Dict[str, Any]:
        """Build timestamp and error update data."""
        update_data = {}

        if started_at:
            update_data["started_at"] = started_at

        if status == SyncJobStatus.COMPLETED and completed_at:
            update_data["completed_at"] = completed_at
        elif status == SyncJobStatus.FAILED:
            if failed_at:
                update_data["failed_at"] = failed_at or datetime.now()
            if error:
                update_data["error"] = error

        return update_data

    async def _update_status_in_database(self, db, sync_job_id: UUID, db_status_value: str) -> None:
        """Update status field using raw SQL."""
        from sqlalchemy import text

        # Update status with uppercase value directly
        await db.execute(
            text(
                "UPDATE sync_job SET status = :status, "
                "modified_at = :modified_at WHERE id = :sync_job_id"
            ),
            {
                "status": db_status_value,
                "modified_at": datetime.now(),
                "sync_job_id": sync_job_id,
            },
        )

    async def update_status(
        self,
        sync_job_id: UUID,
        status: SyncJobStatus,
        current_user: schemas.User,
        stats: Optional[SyncProgressUpdate] = None,
        error: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        failed_at: Optional[datetime] = None,
    ) -> None:
        """Update sync job status with provided details."""
        try:
            async with get_db_context() as db:
                db_sync_job = await crud.sync_job.get(db=db, id=sync_job_id)

                if not db_sync_job:
                    logger.error(f"Sync job {sync_job_id} not found")
                    return

                # Map Python enum to database enum value (lowercase to uppercase)
                db_status_value = map_python_enum_to_database(status)
                logger.info(
                    f"Mapping Python enum {status.value} to database value {db_status_value}"
                )

                update_data = {"status": status}

                if stats:
                    stats_data = self._build_stats_update_data(stats)
                    update_data.update(stats_data)

                timestamp_data = self._build_timestamp_update_data(
                    status, started_at, completed_at, failed_at, error
                )
                update_data.update(timestamp_data)

                # Update status using raw SQL
                await self._update_status_in_database(db, sync_job_id, db_status_value)

                # Update other fields using the normal ORM
                # (excluding status which we already updated)
                update_data.pop("status")
                if update_data:
                    await crud.sync_job.update(
                        db=db,
                        db_obj=db_sync_job,
                        obj_in=schemas.SyncJobUpdate(**update_data),
                        current_user=current_user,
                    )

                await db.commit()
                logger.info(
                    f"Successfully updated sync job {sync_job_id} status to {db_status_value}"
                )

        except Exception as e:
            logger.error(f"Failed to update sync job status: {e}")


# Singleton instance
sync_job_service = SyncJobService()
