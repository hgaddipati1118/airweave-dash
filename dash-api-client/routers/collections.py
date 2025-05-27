"""Collections router for the Airweave Client API."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException

from airweave_client import AirweaveClient, AppUser
from dependencies import get_client, get_user
from models import CreateCollectionRequest, CollectionResponse
from utils import handle_airweave_errors, to_collection_response


router = APIRouter()


@router.post("", response_model=CollectionResponse)
@handle_airweave_errors
async def create_collection(
    request: CreateCollectionRequest,
    client: AirweaveClient = Depends(get_client),
    user: AppUser = Depends(get_user)
):
    """Create a new collection."""
    result = await client.create_collection(
        name=request.name,
        description=request.description,
        custom_id=request.id,
        app_user=user
    )
    return to_collection_response(result)


@router.get("", response_model=List[CollectionResponse])
@handle_airweave_errors
async def list_collections(
    client: AirweaveClient = Depends(get_client),
    user: AppUser = Depends(get_user)
):
    """List all collections."""
    collections = await client.get_collections(app_user=user)
    return [to_collection_response(collection) for collection in collections]


@router.get("/{collection_id}", response_model=Optional[CollectionResponse])
@handle_airweave_errors
async def get_collection(
    collection_id: str,
    client: AirweaveClient = Depends(get_client),
    user: AppUser = Depends(get_user)
):
    """Get a specific collection by ID.
    
    Returns None if the collection is not found, which is expected after deletion.
    """
    collection = await client.get_collection(collection_id=collection_id, app_user=user)
    if collection is None:
        return None
    return to_collection_response(collection)


@router.delete("/{collection_id}")
@handle_airweave_errors
async def delete_collection(
    collection_id: str,
    client: AirweaveClient = Depends(get_client),
    user: AppUser = Depends(get_user)
):
    """Delete a specific collection by ID."""
    await client.delete_collection(collection_id=collection_id, app_user=user)
    return {"message": f"Collection {collection_id} deleted successfully"} 