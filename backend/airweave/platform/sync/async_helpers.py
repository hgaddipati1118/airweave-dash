"""Async helper utilities for improved performance."""

import asyncio
import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, TypeVar

import aiofiles

from airweave.core.config import settings
from airweave.core.logging import logger

# Shared thread pool for CPU-bound operations
_cpu_executor = None
_cpu_executor_lock = asyncio.Lock()

T = TypeVar("T")


async def get_cpu_executor() -> ThreadPoolExecutor:
    """Get or create the shared CPU executor for thread pool operations."""
    global _cpu_executor

    async with _cpu_executor_lock:
        if _cpu_executor is None:
            # Scale with worker count
            max_workers = getattr(settings, "SYNC_THREAD_POOL_SIZE", min(100, os.cpu_count() * 4))

            # Create a thread pool with configurable limits
            _cpu_executor = ThreadPoolExecutor(
                max_workers=max_workers, thread_name_prefix="airweave-cpu"
            )
            logger.info(
                f"🔧 CPU_EXECUTOR_INIT Created shared CPU executor with {max_workers} workers"
            )

    return _cpu_executor


async def run_in_thread_pool(func: Callable[..., T], *args, **kwargs) -> T:
    """Run a synchronous function in the shared thread pool.

    This avoids creating excessive threads by using a controlled thread pool.
    """
    loop = asyncio.get_event_loop()
    executor = await get_cpu_executor()

    # If there are keyword arguments, wrap the function with partial
    if kwargs:
        from functools import partial

        func = partial(func, **kwargs)
        return await loop.run_in_executor(executor, func, *args)
    else:
        return await loop.run_in_executor(executor, func, *args)


async def compute_file_hash_async(file_path: str) -> str:
    """Compute file hash asynchronously without blocking the event loop."""
    hash_obj = hashlib.sha256()

    async with aiofiles.open(file_path, "rb") as f:
        # Read file in chunks to avoid memory issues
        chunk_size = 8192
        while True:
            chunk = await f.read(chunk_size)
            if not chunk:
                break
            # Hash update is CPU-bound, run in thread
            await run_in_thread_pool(hash_obj.update, chunk)

    return hash_obj.hexdigest()


async def compute_content_hash_async(content: str) -> str:
    """Compute hash of content asynchronously."""

    def _compute_hash(data: str) -> str:
        return hashlib.sha256(data.encode()).hexdigest()

    return await run_in_thread_pool(_compute_hash, content)


def stable_serialize(obj: Any) -> Any:
    """Serialize object in a stable way for hashing."""
    if isinstance(obj, dict):
        return {k: stable_serialize(v) for k, v in sorted(obj.items())}
    elif isinstance(obj, (list, tuple)):
        return [stable_serialize(x) for x in obj]
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    else:
        return str(obj)


async def compute_entity_hash_async(entity: Any) -> str:
    """Compute entity hash asynchronously.

    Args:
        entity: BaseEntity instance or dict

    Returns:
        Hash string
    """
    # Check if entity already has a cached hash
    if hasattr(entity, "_hash") and entity._hash:
        return entity._hash

    # Import here to avoid circular imports
    from airweave.platform.entities._base import FileEntity

    # Handle FileEntity specially
    if isinstance(entity, FileEntity) and entity.local_path:
        try:
            hash_value = await compute_file_hash_async(entity.local_path)
            # Cache the hash
            entity._hash = hash_value
            return hash_value
        except Exception:
            # Fall back to metadata hash
            pass

    # For regular entities, compute hash from content fields
    def _compute_entity_hash(entity_obj) -> str:
        # Define metadata fields to exclude
        metadata_fields = {
            "sync_job_id",
            "vector",
            "_hash",
            "db_entity_id",
            "source_name",
            "sync_id",
            "sync_metadata",
            "created_at",
            "updated_at",
            "modified_at",
            "_sa_instance_state",  # SQLAlchemy internal state
            "organization_id",
            "chunk_index",  # Exclude chunk_index from hash to ensure parent/chunk compatibility
        }

        # Get content fields
        if hasattr(entity_obj, "model_dump"):
            # Pydantic model
            all_fields = set(entity_obj.model_fields.keys())
            data = entity_obj.model_dump()
        else:
            # Dict
            all_fields = set(entity_obj.keys())
            data = entity_obj

        content_fields = all_fields - metadata_fields

        # Extract only content fields
        content_data = {k: v for k, v in data.items() if k in content_fields}

        # Use stable serialization
        stable_data = stable_serialize(content_data)
        import json

        json_str = json.dumps(stable_data, sort_keys=True, separators=(",", ":"))

        return hashlib.sha256(json_str.encode()).hexdigest()

    hash_value = await run_in_thread_pool(_compute_entity_hash, entity)

    # Cache the hash if entity is an object
    if hasattr(entity, "_hash"):
        entity._hash = hash_value

    return hash_value


class AsyncBatcher:
    """Batch async operations to reduce overhead."""

    def __init__(self, batch_size: int = 10, timeout: float = 0.1):
        """Initialize the async batcher.

        Args:
            batch_size: Maximum number of items to batch together
            timeout: Maximum time to wait for batch to fill
        """
        self.batch_size = batch_size
        self.timeout = timeout
        self._queue: asyncio.Queue = asyncio.Queue()
        self._results: Dict[int, asyncio.Future] = {}
        self._counter = 0
        self._processor_task = None

    async def start(self, processor: Callable[[List[Any]], List[Any]]):
        """Start the batch processor."""
        self._processor_task = asyncio.create_task(self._process_batches(processor))

    async def stop(self):
        """Stop the batch processor."""
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass

    async def submit(self, item: Any) -> Any:
        """Submit an item for batched processing."""
        future = asyncio.Future()
        item_id = self._counter
        self._counter += 1
        self._results[item_id] = future

        await self._queue.put((item_id, item))
        return await future

    async def _process_batches(self, processor: Callable):
        """Process items in batches."""
        while True:
            batch = []
            batch_ids = []

            try:
                # Wait for first item with timeout
                first_item = await asyncio.wait_for(self._queue.get(), timeout=self.timeout)
                item_id, item = first_item
                batch.append(item)
                batch_ids.append(item_id)

                # Collect more items up to batch size
                while len(batch) < self.batch_size and not self._queue.empty():
                    item_id, item = await self._queue.get()
                    batch.append(item)
                    batch_ids.append(item_id)

                # Process batch if we have items
                if batch:
                    await self._process_single_batch(processor, batch, batch_ids)

            except asyncio.TimeoutError:
                # Process any pending items on timeout
                if batch:
                    await self._process_single_batch(processor, batch, batch_ids)
            except asyncio.CancelledError:
                # Clean up on cancellation
                for future in self._results.values():
                    future.cancel()
                raise

    async def _process_single_batch(
        self, processor: Callable, batch: List[Any], batch_ids: List[int]
    ):
        """Process a single batch of items."""
        try:
            results = await processor(batch)
            # Deliver results
            for item_id, result in zip(batch_ids, results, strict=False):
                if item_id in self._results:
                    self._results[item_id].set_result(result)
                    del self._results[item_id]
        except Exception as e:
            # Deliver errors
            for item_id in batch_ids:
                if item_id in self._results:
                    self._results[item_id].set_exception(e)
                    del self._results[item_id]
