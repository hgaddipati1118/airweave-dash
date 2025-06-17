"""API endpoints for collections."""

from typing import List

from fastapi import BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.router import TrailingSlashRouter
from airweave.core.collection_service import collection_service
from airweave.core.search_service import ResponseType, search_service
from airweave.core.source_connection_service import source_connection_service
from airweave.core.sync_service import sync_service
from airweave.core.temporal_service import temporal_service
from airweave.models.user import User

router = TrailingSlashRouter()


@router.get("/", response_model=List[schemas.Collection])
async def list_collections(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> List[schemas.Collection]:
    """List all collections for the current user's organization."""
    return await crud.collection.get_multi_by_organization(
        db,
        organization_id=current_user.organization_id,
        current_user=current_user,
        skip=skip,
        limit=limit,
    )


@router.post("/", response_model=schemas.Collection)
async def create_collection(
    collection: schemas.CollectionCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> schemas.Collection:
    """Create a new collection."""
    return await collection_service.create(db, collection_in=collection, current_user=current_user)


@router.get("/{readable_id}", response_model=schemas.Collection)
async def get_collection(
    readable_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> schemas.Collection:
    """Get a specific collection by its readable ID."""
    db_obj = await crud.collection.get_by_readable_id(
        db, readable_id=readable_id, current_user=current_user
    )
    if db_obj is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return db_obj


@router.patch("/{readable_id}", response_model=schemas.Collection)
async def update_collection(
    readable_id: str,
    collection: schemas.CollectionUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> schemas.Collection:
    """Update a collection by its readable ID."""
    db_obj = await crud.collection.get_by_readable_id(
        db, readable_id=readable_id, current_user=current_user
    )
    if db_obj is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return await crud.collection.update(
        db, db_obj=db_obj, obj_in=collection, current_user=current_user
    )


@router.delete("/{readable_id}", response_model=schemas.Collection)
async def delete_collection(
    readable_id: str,
    delete_data: bool = False,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> schemas.Collection:
    """Delete a collection by its readable ID.

    Args:
        readable_id: The readable ID of the collection to delete
        delete_data: Whether to delete the data in destinations
        db: The database session
        current_user: The current user

    Returns:
        The deleted collection
    """
    # Find the collection
    db_obj = await crud.collection.get_by_readable_id(
        db, readable_id=readable_id, current_user=current_user
    )
    if db_obj is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    # If delete_data is true, we need to delete data in destination systems
    # before deleting the collection (which will cascade delete source connections)
    if delete_data:
        # Note: This should be moved to a service method that can properly
        # handle the destination data deletion without requiring multiple queries
        pass

    # Delete the collection - CASCADE will handle all child objects
    return await crud.collection.remove(db, id=db_obj.id, current_user=current_user)


@router.get("/{readable_id}/search", response_model=schemas.SearchResponse)
async def search_collection(
    readable_id: str,
    query: str = Query(..., description="Search query"),
    response_type: ResponseType = Query(
        ResponseType.RAW, description="Type of response: raw search results or AI completion"
    ),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> schemas.SearchResponse:
    """Search within a collection identified by readable ID.

    Args:
        readable_id: The readable ID of the collection to search
        query: The search query
        response_type: Type of response (raw results or AI completion)
        db: The database session
        current_user: The current user

    Returns:
        dict: Search results or AI completion response
    """
    try:
        return await search_service.search_with_completion(
            db,
            readable_id=readable_id,
            query=query,
            current_user=current_user,
            response_type=response_type,
        )
    except Exception as e:
        # Log the error for debugging
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Search error for collection {readable_id}: {str(e)}")

        # Check if it's a connection error
        error_message = str(e).lower()
        if (
            "connection" in error_message
            or "refused" in error_message
            or "timeout" in error_message
        ):
            raise HTTPException(
                status_code=503,
                detail="Vector database service is currently unavailable. Please try again later.",
            ) from e
        elif "not found" in error_message:
            raise HTTPException(
                status_code=404,
                detail=f"Collection '{readable_id}' not found or you don't have access to it.",
            ) from e
        else:
            # For other errors, return a generic message but with 500 status
            raise HTTPException(
                status_code=500, detail=f"An error occurred while searching: {str(e)}"
            ) from e


@router.post("/{readable_id}/refresh_all", response_model=list[schemas.SourceConnectionJob])
async def refresh_all_source_connections(
    *,
    readable_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
    background_tasks: BackgroundTasks,
) -> list[schemas.SourceConnectionJob]:
    """Start sync jobs for all source connections in the collection.

    Args:
        readable_id: The readable ID of the collection
        db: The database session
        current_user: The current user
        background_tasks: Background tasks for async operations

    Returns:
        A list of created sync jobs
    """
    # Check if collection exists
    collection = await crud.collection.get_by_readable_id(
        db, readable_id=readable_id, current_user=current_user
    )
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Convert to Pydantic model immediately
    collection_obj = schemas.Collection.model_validate(collection, from_attributes=True)

    # Get all source connections for this collection
    source_connections = await source_connection_service.get_source_connections_by_collection(
        db=db, collection=readable_id, current_user=current_user
    )

    if not source_connections:
        return []

    # Create a sync job for each source connection and run it in the background
    sync_jobs = []

    for sc in source_connections:
        # Create the sync job
        sync_job = await source_connection_service.run_source_connection(
            db=db, source_connection_id=sc.id, current_user=current_user
        )

        # Get necessary objects for running the sync
        sync = await crud.sync.get(
            db=db, id=sync_job.sync_id, current_user=current_user, with_connections=True
        )
        sync_dag = await sync_service.get_sync_dag(
            db=db, sync_id=sync_job.sync_id, current_user=current_user
        )

        # Get source connection with auth_fields for temporal processing
        source_connection = await source_connection_service.get_source_connection(
            db=db,
            source_connection_id=sc.id,
            show_auth_fields=True,  # Important: Need actual auth_fields for temporal
            current_user=current_user,
        )

        # Prepare objects for background task
        sync = schemas.Sync.model_validate(sync, from_attributes=True)
        sync_dag = schemas.SyncDag.model_validate(sync_dag, from_attributes=True)
        source_connection = schemas.SourceConnection.from_orm_with_collection_mapping(
            source_connection
        )

        # Add to jobs list
        sync_jobs.append(sync_job.to_source_connection_job(sc.id))

        # Start the sync job in the background or via Temporal
        if await temporal_service.is_temporal_enabled():
            # Use Temporal workflow
            await temporal_service.run_source_connection_workflow(
                sync=sync,
                sync_job=sync_job,
                sync_dag=sync_dag,
                collection=collection_obj,  # Use the already converted object
                source_connection=source_connection,
                user=current_user,
            )
        else:
            # Fall back to background tasks
            background_tasks.add_task(
                sync_service.run,
                sync,
                sync_job,
                sync_dag,
                collection_obj,  # Use the already converted object
                source_connection,
                current_user,
            )

    return sync_jobs
