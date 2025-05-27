"""Connections router for the Airweave Client API."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException

from airweave_client import AirweaveClient, AppUser
from dependencies import get_client, get_user
from models import CreateConnectionRequest, ConnectionConfig, ConnectionResponse
from utils import handle_airweave_errors, to_connection_response
from connection_configs import get_connection_config, validate_connection_config


router = APIRouter()


@router.post("", response_model=ConnectionResponse)
@handle_airweave_errors
async def create_connection(
    request: CreateConnectionRequest,
    client: AirweaveClient = Depends(get_client),
    user: AppUser = Depends(get_user)
):
    """Create a new connection."""
    # Get and validate connection specification
    spec = get_connection_config(request.source_type.value)
    if not spec:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported connection type: {request.source_type.value}"
        )
    
    validation_errors = validate_connection_config(request.source_type.value, request.config)
    if validation_errors:
        raise HTTPException(status_code=400, detail={"errors": validation_errors})
    
    # Separate auth and config fields
    auth_fields = {
        field: request.config[field]
        for field in spec["auth_config"]["required_fields"] + spec["auth_config"]["optional_fields"]
        if field in request.config
    }
    
    all_auth_fields = spec["auth_config"]["required_fields"] + spec["auth_config"]["optional_fields"]
    config_fields = {
        k: v for k, v in request.config.items()
        if k not in all_auth_fields
    }
    
    # Create connection
    connection_config = ConnectionConfig(
        name=request.name,
        source_type=request.source_type,
        collection_id=request.collection_id,
        auth_fields=auth_fields,
        config_fields=config_fields if config_fields else None
    )
    
    result = await client.create_connection(config=connection_config, app_user=user)
    return to_connection_response(result)


@router.get("", response_model=List[ConnectionResponse])
@handle_airweave_errors
async def list_connections(
    collection_id: Optional[str] = Query(None, description="Filter by collection ID"),
    client: AirweaveClient = Depends(get_client),
    user: AppUser = Depends(get_user)
):
    """List all connections, optionally filtered by collection ID."""
    # Pass collection_id to the client for efficient database-level filtering
    connections = await client.get_connections(collection_id=collection_id, app_user=user)
    
    return [to_connection_response(connection) for connection in connections]


@router.get("/{connection_id}", response_model=ConnectionResponse)
@handle_airweave_errors
async def get_connection(
    connection_id: str,
    client: AirweaveClient = Depends(get_client),
    user: AppUser = Depends(get_user)
):
    """Get a specific connection by ID."""
    connection = await client.get_connection(connection_id=connection_id, app_user=user)
    return to_connection_response(connection)


@router.delete("/{connection_id}")
@handle_airweave_errors
async def delete_connection(
    connection_id: str,
    client: AirweaveClient = Depends(get_client),
    user: AppUser = Depends(get_user)
):
    """Delete a specific connection by ID."""
    await client.delete_connection(connection_id=connection_id, app_user=user)
    return {"message": f"Connection {connection_id} deleted successfully"} 