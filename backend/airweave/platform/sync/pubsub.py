"""Pubsub for sync jobs using Redis backend."""

import asyncio
import platform
from uuid import UUID

import redis.asyncio as redis
from pydantic import BaseModel

from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.core.redis_client import redis_client


class SyncProgressUpdate(BaseModel):
    """Sync progress update data structure.

    This is sent over the pubsub channel to subscribers
    """

    inserted: int = 0
    updated: int = 0
    deleted: int = 0
    kept: int = 0
    skipped: int = 0
    entities_encountered: dict[str, int] = {}
    is_complete: bool = False
    is_failed: bool = False


PUBLISH_THRESHOLD = 3


class SyncPubSub:
    """Manages sync job pubsub using Redis."""

    def _channel_name(self, job_id: UUID) -> str:
        """Generate channel name for a sync job.

        Args:
            job_id: The sync job ID.

        Returns:
            str: The channel name.
        """
        return f"sync_job:{job_id}"

    async def publish(self, job_id: UUID, update: SyncProgressUpdate) -> None:
        """Publish an update to a sync job channel.

        Note: Redis channels are created on-demand when someone subscribes.
        Publishing to a non-existent channel (no subscribers) is a no-op.

        Args:
            job_id: The sync job ID.
            update: The progress update to publish.
        """
        channel = self._channel_name(job_id)
        message = update.model_dump_json()

        subscribers = await redis_client.publish(channel, message)

        if subscribers > 0:
            logger.info(f"Published update to {subscribers} subscribers for job {job_id}")

    async def subscribe(self, job_id: UUID) -> redis.client.PubSub:
        """Create a new pubsub instance and subscribe to a sync job's updates.

        Args:
            job_id: The sync job ID to subscribe to.

        Returns:
            redis.client.PubSub: A new Redis pubsub instance subscribed to this job's channel.
        """
        channel = self._channel_name(job_id)

        # Get socket keepalive options based on OS
        if platform.system() == "Darwin":
            socket_keepalive_options = {}
        else:
            # Use the correct Linux TCP keepalive constants
            import socket

            if hasattr(socket, "TCP_KEEPIDLE"):
                socket_keepalive_options = {
                    socket.TCP_KEEPIDLE: 60,  # Start keepalive after 60s idle
                    socket.TCP_KEEPINTVL: 10,  # Interval between keepalive probes
                    socket.TCP_KEEPCNT: 6,  # Number of keepalive probes
                }
            else:
                socket_keepalive_options = {}

        # Build Redis URL with authentication
        if settings.REDIS_PASSWORD:
            redis_url = f"redis://:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
        else:
            redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"

        # Create a new Redis client directly for pubsub to avoid connection pool issues
        # This is a workaround for async pubsub issues in Docker environments
        pubsub_redis = await redis.from_url(
            redis_url,
            decode_responses=True,
            socket_keepalive=True,
            socket_connect_timeout=5,
            # Don't set socket_timeout for pubsub connections - they need to stay open
            socket_keepalive_options=socket_keepalive_options,
        )

        # Create pubsub instance
        pubsub = pubsub_redis.pubsub()

        # Subscribe to the specific channel
        await pubsub.subscribe(channel)

        logger.info(f"Created new pubsub subscription for sync job {job_id}")
        return pubsub


class SyncProgress:
    """Tracks sync progress and automatically publishes updates."""

    def __init__(self, job_id: UUID):
        """Initialize the SyncProgress instance."""
        self.job_id = job_id
        self.stats = SyncProgressUpdate()
        self._last_published = 0
        self._publish_threshold = PUBLISH_THRESHOLD
        # CRITICAL FIX: Add async lock to prevent race conditions
        self._lock = asyncio.Lock()

    def __getattr__(self, name: str) -> int:
        """Get counter value for any stat."""
        return getattr(self.stats, name)

    async def increment(self, stat_name: str, amount: int = 1) -> None:
        """Increment a counter and trigger update if threshold reached.

        Uses async lock to prevent race conditions from concurrent workers.
        """
        async with self._lock:  # CRITICAL FIX: Synchronize access
            current_value = getattr(self.stats, stat_name, 0)
            setattr(self.stats, stat_name, current_value + amount)

            # Include ALL operations in threshold calculation (including skipped)
            total_ops = sum(
                [
                    self.stats.inserted,
                    self.stats.updated,
                    self.stats.deleted,
                    self.stats.kept,
                    self.stats.skipped,
                ]
            )

            # Check if we should publish
            if total_ops - self._last_published >= self._publish_threshold:
                logger.info(f"Progress threshold reached: {total_ops} total ops, publishing update")
                await self._publish()
                self._last_published = total_ops
            else:
                logger.debug(
                    f"Progress: {stat_name}={current_value + amount}, total={total_ops}, "
                    f"threshold={self._publish_threshold}"
                )

    async def _publish(self) -> None:
        """Publish current progress."""
        await sync_pubsub.publish(self.job_id, self.stats)

    async def finalize(self, is_complete: bool = True) -> None:
        """Publish final progress."""
        async with self._lock:  # Ensure finalize is also synchronized
            self.stats.is_complete = is_complete
            self.stats.is_failed = not is_complete
            await self._publish()

    def to_dict(self) -> dict:
        """Convert progress to a dictionary."""
        return self.stats.model_dump()

    async def update_entities_encountered_count(
        self, entities_encountered: dict[str, set[str]]
    ) -> None:
        """Update the entities encountered tracking."""
        async with self._lock:  # Synchronize this as well
            self.stats.entities_encountered = {
                entity_type: len(entity_ids)
                for entity_type, entity_ids in entities_encountered.items()
            }


# Create a global instance for the entire app
sync_pubsub = SyncPubSub()
