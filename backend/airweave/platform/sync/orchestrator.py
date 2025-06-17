"""Module for data synchronization with improved architecture."""

from datetime import datetime
from typing import Optional

from airweave import schemas
from airweave.core.shared_models import SyncJobStatus
from airweave.core.sync_job_service import sync_job_service
from airweave.platform.sync.context import SyncContext
from airweave.platform.sync.entity_processor import EntityProcessor
from airweave.platform.sync.stream import AsyncSourceStream
from airweave.platform.sync.worker_pool import AsyncWorkerPool


class SyncOrchestrator:
    """Orchestrates data synchronization from sources to destinations.

    Uses a pull-based approach where entities are only pulled from the
    stream when a worker is available to process them immediately.
    """

    def __init__(
        self,
        entity_processor: EntityProcessor,
        worker_pool: AsyncWorkerPool,
        sync_context: SyncContext,
    ):
        """Initialize the sync orchestrator.

        Args:
            entity_processor: Processes entities through transformation pipeline
            worker_pool: Manages concurrent task execution with semaphore control
            sync_context: Contains all resources needed for synchronization
        """
        self.entity_processor = entity_processor
        self.worker_pool = worker_pool
        self.sync_context = sync_context

        # Queue size provides buffering for bursty sources
        # Workers pull from this queue when ready
        self.stream_buffer_size = 100

    async def run(self) -> schemas.Sync:
        """Execute the synchronization process.

        Returns:
            The sync object after completion

        Raises:
            Exception: If sync fails, after updating job status
        """
        try:
            await self._start_sync()
            await self._process_entities()
            await self._complete_sync()

            return self.sync_context.sync

        except Exception as e:
            await self._handle_sync_failure(e)
            raise

    async def _start_sync(self) -> None:
        """Initialize sync job and update status to in-progress."""
        self.sync_context.logger.info(
            f"Starting sync job {self.sync_context.sync_job.id} for sync "
            f"{self.sync_context.sync.id}"
        )

        await sync_job_service.update_status(
            sync_job_id=self.sync_context.sync_job.id,
            status=SyncJobStatus.IN_PROGRESS,
            current_user=self.sync_context.current_user,
            started_at=datetime.now(),
        )

    async def _process_entities(self) -> None:
        """Process entities with pull-based concurrency control.

        Only pulls an entity from the stream when a worker is available,
        ensuring natural backpressure throughout the pipeline.
        """
        source_node = self.sync_context.dag.get_source_node()

        self.sync_context.logger.info(
            f"Starting pull-based processing from source {self.sync_context.source._name} "
            f"(buffer: {self.stream_buffer_size}, max workers: {self.worker_pool.max_workers})"
        )

        stream_error: Optional[Exception] = None

        try:
            async with AsyncSourceStream(
                self.sync_context.source.generate_entities(),
                queue_size=self.stream_buffer_size,
                logger=self.sync_context.logger,
            ) as stream:
                async for entity in stream.get_entities():
                    # Handle skipped entities without using a worker
                    if getattr(entity, "should_skip", False):
                        self.sync_context.logger.debug(f"Skipping entity: {entity.entity_id}")
                        await self.sync_context.progress.increment("skipped")
                        continue

                    # Wait for a worker slot before processing
                    # This creates natural backpressure - we only pull the next entity
                    # when we have capacity to process it
                    async with self.worker_pool.semaphore:
                        await self.entity_processor.process(
                            entity=entity,
                            source_node=source_node,
                            sync_context=self.sync_context,
                        )

        except Exception as e:
            stream_error = e
            self.sync_context.logger.error(f"Error during entity streaming: {e}")
            raise

        finally:
            # No need to wait for completion - all processing is done inline
            await self.sync_context.progress.finalize(is_complete=(stream_error is None))

    async def _complete_sync(self) -> None:
        """Mark sync job as completed with final statistics."""
        stats = getattr(self.sync_context.progress, "stats", None)

        await sync_job_service.update_status(
            sync_job_id=self.sync_context.sync_job.id,
            status=SyncJobStatus.COMPLETED,
            current_user=self.sync_context.current_user,
            completed_at=datetime.now(),
            stats=stats,
        )

        self.sync_context.logger.info(
            f"Completed sync job {self.sync_context.sync_job.id} successfully. Stats: {stats}"
        )

    async def _handle_sync_failure(self, error: Exception) -> None:
        """Handle sync failure by updating job status with error details."""
        self.sync_context.logger.error(
            f"Sync job {self.sync_context.sync_job.id} failed: {error}", exc_info=True
        )

        stats = getattr(self.sync_context.progress, "stats", None)

        await sync_job_service.update_status(
            sync_job_id=self.sync_context.sync_job.id,
            status=SyncJobStatus.FAILED,
            current_user=self.sync_context.current_user,
            error=str(error),
            failed_at=datetime.now(),
            stats=stats,
        )
