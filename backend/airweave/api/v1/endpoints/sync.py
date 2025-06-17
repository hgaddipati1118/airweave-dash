"""API endpoints for managing syncs."""

import asyncio
import json
from typing import AsyncGenerator, List, Optional, Union
from uuid import UUID

from fastapi import BackgroundTasks, Body, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.router import TrailingSlashRouter
from airweave.core.logging import logger
from airweave.core.sync_service import sync_service
from airweave.platform.sync.pubsub import sync_pubsub

router = TrailingSlashRouter()


@router.get("/", response_model=Union[list[schemas.Sync], list[schemas.SyncWithSourceConnection]])
async def list_syncs(
    *,
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    with_source_connection: bool = False,
    user: schemas.User = Depends(deps.get_user),
) -> list[schemas.Sync] | list[schemas.SyncWithSourceConnection]:
    """List all syncs for the current user.

    Args:
    -----
        db: The database session
        skip: The number of syncs to skip
        limit: The number of syncs to return
        with_source_connection: Whether to include the source connection in the response
        user: The current user

    Returns:
    --------
        list[schemas.Sync] | list[schemas.SyncWithSourceConnection]: A list of syncs
    """
    return await sync_service.list_syncs(
        db=db,
        current_user=user,
        skip=skip,
        limit=limit,
        with_source_connection=with_source_connection,
    )


@router.get("/jobs", response_model=list[schemas.SyncJob])
async def list_all_jobs(
    *,
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    status: Optional[List[str]] = Query(None, description="Filter by job status"),
    user: schemas.User = Depends(deps.get_user),
) -> list[schemas.SyncJob]:
    """List all jobs across all syncs.

    Args:
    -----
        db: The database session
        skip: The number of jobs to skip
        limit: The number of jobs to return
        status: Filter by job status
        user: The current user

    Returns:
    --------
        list[schemas.SyncJob]: A list of all sync jobs
    """
    return await sync_service.list_sync_jobs(
        db=db, current_user=user, skip=skip, limit=limit, status=status
    )


@router.get("/{sync_id}", response_model=schemas.Sync)
async def get_sync(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.Sync:
    """Get a specific sync by ID.

    Args:
    -----
        db: The database session
        sync_id: The ID of the sync to get
        user: The current user

    Returns:
    --------
        sync (schemas.Sync): The sync
    """
    return await sync_service.get_sync(db=db, sync_id=sync_id, current_user=user)


@router.post("/", response_model=schemas.Sync)
async def create_sync(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_in: schemas.SyncCreate = Body(...),
    user: schemas.User = Depends(deps.get_user),
    background_tasks: BackgroundTasks,
) -> schemas.Sync:
    """Create a new sync configuration.

    Args:
    -----
        db: The database session
        sync_in: The sync to create
        user: The current user
        background_tasks: The background tasks

    Returns:
    --------
        sync (schemas.Sync): The created sync
    """
    # Create the sync and sync job - kinda, not really, we'll do that in the background
    sync, sync_job = await sync_service.create_and_run_sync(
        db=db, sync_in=sync_in, current_user=user
    )
    source_connection = await crud.source_connection.get(
        db=db, id=sync_in.source_connection_id, current_user=user
    )
    collection = await crud.collection.get_by_readable_id(
        db=db, readable_id=source_connection.readable_collection_id, current_user=user
    )
    collection = schemas.Collection.model_validate(collection, from_attributes=True)

    source_connection = schemas.SourceConnection.model_validate(
        source_connection, from_attributes=True
    )

    # If job was created and should run immediately, start it in background
    if sync_job and sync_in.run_immediately:
        sync_dag = await sync_service.get_sync_dag(db=db, sync_id=sync.id, current_user=user)
        background_tasks.add_task(
            sync_service.run, sync, sync_job, sync_dag, collection, source_connection, user
        )

    return sync


@router.delete("/{sync_id}", response_model=schemas.Sync)
async def delete_sync(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    delete_data: bool = False,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.Sync:
    """Delete a sync configuration and optionally its associated data.

    Args:
    -----
        db: The database session
        sync_id: The ID of the sync to delete
        delete_data: Whether to delete the data associated with the sync
        user: The current user

    Returns:
    --------
        sync (schemas.Sync): The deleted sync
    """
    return await sync_service.delete_sync(
        db=db, sync_id=sync_id, current_user=user, delete_data=delete_data
    )


@router.post("/{sync_id}/run", response_model=schemas.SyncJob)
async def run_sync(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    user: schemas.User = Depends(deps.get_user),
    background_tasks: BackgroundTasks,
) -> schemas.SyncJob:
    """Trigger a sync run.

    Args:
    -----
        db: The database session
        sync_id: The ID of the sync to run
        user: The current user
        background_tasks: The background tasks

    Returns:
    --------
        sync_job (schemas.SyncJob): The sync job
    """
    # Trigger the sync run - kinda, not really, we'll do that in the background
    sync, sync_job, sync_dag = await sync_service.trigger_sync_run(
        db=db, sync_id=sync_id, current_user=user
    )

    # Start the sync job in the background - this is where the sync actually runs
    background_tasks.add_task(sync_service.run, sync, sync_job, sync_dag, user)

    return sync_job


@router.get("/{sync_id}/jobs", response_model=list[schemas.SyncJob])
async def list_sync_jobs(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    user: schemas.User = Depends(deps.get_user),
) -> list[schemas.SyncJob]:
    """List all jobs for a specific sync.

    Args:
    -----
        db: The database session
        sync_id: The ID of the sync to list jobs for
        user: The current user

    Returns:
    --------
        list[schemas.SyncJob]: A list of sync jobs
    """
    return await sync_service.list_sync_jobs(db=db, current_user=user, sync_id=sync_id)


@router.get("/{sync_id}/job/{job_id}", response_model=schemas.SyncJob)
async def get_sync_job(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    job_id: UUID,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.SyncJob:
    """Get details of a specific sync job.

    Args:
    -----
        db: The database session
        sync_id: The ID of the sync to list jobs for
        job_id: The ID of the job to get
        user: The current user

    Returns:
    --------
        sync_job (schemas.SyncJob): The sync job
    """
    return await sync_service.get_sync_job(db=db, job_id=job_id, current_user=user, sync_id=sync_id)


@router.get("/job/{job_id}/subscribe")
async def subscribe_sync_job(
    job_id: UUID,
    user: schemas.User = Depends(deps.get_user),  # Standard dependency injection
) -> StreamingResponse:
    """Server-Sent Events (SSE) endpoint to subscribe to a sync job's progress.

    Args:
    -----
        job_id: The ID of the job to subscribe to
        user: The authenticated user (from standard dependency injection)

    Returns:
    --------
        StreamingResponse: The streaming response
    """
    logger.info(f"SSE sync subscription authenticated for user: {user.id}, job: {job_id}")

    # Track active SSE connections
    connection_id = f"{user.id}:{job_id}:{asyncio.get_event_loop().time()}"

    # Get a new pubsub instance subscribed to this job
    pubsub = await sync_pubsub.subscribe(job_id)

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'job_id': str(job_id)})}\n\n"

            # Send heartbeat every 30 seconds to keep connection alive
            last_heartbeat = asyncio.get_event_loop().time()
            heartbeat_interval = 30  # seconds

            async for message in pubsub.listen():
                # Check if we need to send a heartbeat
                current_time = asyncio.get_event_loop().time()
                if current_time - last_heartbeat > heartbeat_interval:
                    yield 'data: {"type": "heartbeat"}\n\n'
                    last_heartbeat = current_time

                if message["type"] == "message":
                    # Parse and forward the sync progress update
                    yield f"data: {message['data']}\n\n"
                elif message["type"] == "subscribe":
                    # Log subscription confirmation
                    logger.info(f"SSE subscribed to job {job_id} for connection {connection_id}")

        except asyncio.CancelledError:
            logger.info(f"SSE connection cancelled for job {job_id}, connection: {connection_id}")
        except Exception as e:
            logger.error(f"SSE error for job {job_id}: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            # Clean up when SSE connection closes
            try:
                await pubsub.close()
            except Exception as e:
                logger.warning(f"Error closing pubsub for job {job_id}: {e}")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
            "Content-Type": "text/event-stream",
            "Access-Control-Allow-Origin": "*",  # Adjust for your CORS needs
        },
    )


@router.get("/{sync_id}/dag", response_model=schemas.SyncDag)
async def get_sync_dag(
    sync_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    user: schemas.User = Depends(deps.get_user),
) -> schemas.SyncDag:
    """Get the DAG for a specific sync."""
    return await sync_service.get_sync_dag(db=db, sync_id=sync_id, current_user=user)


@router.patch("/{sync_id}", response_model=schemas.Sync)
async def update_sync(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    sync_update: schemas.SyncUpdate = Body(...),
    user: schemas.User = Depends(deps.get_user),
) -> schemas.Sync:
    """Update a sync configuration.

    Args:
    -----
        db: The database session
        sync_id: The ID of the sync to update
        sync_update: The sync update data
        user: The current user

    Returns:
    --------
        sync (schemas.Sync): The updated sync
    """
    return await sync_service.update_sync(
        db=db, sync_id=sync_id, sync_update=sync_update, current_user=user
    )
