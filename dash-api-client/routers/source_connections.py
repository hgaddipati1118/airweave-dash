"""Source connections router for the Airweave Client API."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException

from airweave_client import AirweaveClient, AppUser
from dependencies import get_client, get_user
from models import SyncResponse
from utils import handle_airweave_errors


router = APIRouter()


@router.post("/{connection_id}/run", response_model=SyncResponse)
@handle_airweave_errors
async def run_source_connection(
    connection_id: str,
    access_token: Optional[str] = None,
    client: AirweaveClient = Depends(get_client),
    user: AppUser = Depends(get_user)
):
    """Run a sync for a source connection.
    
    Args:
        connection_id: The ID of the source connection to run
        access_token: Optional access token to use instead of stored credentials
        client: The Airweave client
        user: The current user
        
    Returns:
        The created sync job
    """
    result = await client.sync_connection(
        connection_id=connection_id,
        access_token=access_token,
        app_user=user
    )
    
    return SyncResponse(
        sync_id=result.id,
        connection_id=result.connection_id,
        status=result.status,
        started_at=result.created_at.isoformat() if result.created_at else None
    ) 