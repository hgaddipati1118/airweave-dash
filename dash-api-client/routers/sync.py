"""Sync router for the Airweave Client API."""

from fastapi import APIRouter, Depends, Query

from airweave_client import AirweaveClient, AppUser
from dependencies import get_client, get_user
from models import TriggerSyncRequest, SyncResponse, SyncStatusResponse, LatestSyncResponse
from utils import handle_airweave_errors


router = APIRouter()


@router.post("", response_model=SyncResponse)
@handle_airweave_errors
async def trigger_sync(
    request: TriggerSyncRequest,
    client: AirweaveClient = Depends(get_client),
    user: AppUser = Depends(get_user)
):
    """Trigger a sync for a connection."""
    result = await client.sync_connection(
        connection_id=request.connection_id,
        app_user=user
    )
    
    return SyncResponse(
        sync_id=result.id,
        connection_id=result.connection_id,
        status=result.status,
        started_at=result.created_at.isoformat() if result.created_at else None
    )


@router.get("/latest/{connection_id}", response_model=SyncStatusResponse)
@handle_airweave_errors
async def get_latest_sync_status(
    connection_id: str,
    client: AirweaveClient = Depends(get_client),
    user: AppUser = Depends(get_user)
):
    """Get the latest sync status for a connection."""
    result = await client.get_latest_sync_status(connection_id, app_user=user)
    
    if not result:
        return SyncStatusResponse(
            sync_id="",
            connection_id=connection_id,
            status="no_syncs",
            started_at=None,
            completed_at=None,
            error_message="No sync jobs found for this connection"
        )
    
    return SyncStatusResponse(
        sync_id=result.id,
        connection_id=result.connection_id,
        status=result.status,
        started_at=result.created_at.isoformat() if result.created_at else None,
        completed_at=result.completed_at.isoformat() if result.completed_at else None,
        error_message=result.error_message
    )

