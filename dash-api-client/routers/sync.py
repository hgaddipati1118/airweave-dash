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


@router.get("/{sync_id}/status", response_model=SyncStatusResponse)
@handle_airweave_errors
async def get_sync_status(
    sync_id: str,
    connection_id: str = Query(..., description="The ID of the connection"),
    client: AirweaveClient = Depends(get_client),
    user: AppUser = Depends(get_user)
):
    """Get the status of a sync job."""
    result = await client.get_sync_job(sync_id, connection_id, app_user=user)
    
    return SyncStatusResponse(
        sync_id=result.id,
        connection_id=result.connection_id,
        status=result.status,
        started_at=result.created_at.isoformat() if result.created_at else None,
        completed_at=result.completed_at.isoformat() if hasattr(result, 'completed_at') and result.completed_at else None,
        error_message=result.error_message if hasattr(result, 'error_message') else None
    )

