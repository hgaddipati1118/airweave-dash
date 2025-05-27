"""Search router for the Airweave Client API."""

from fastapi import APIRouter, Depends, HTTPException

from airweave_client import AirweaveClient, AppUser
from dependencies import get_client, get_user
from models import SearchRequest, SearchResponse
from utils import handle_airweave_errors


router = APIRouter()


@router.post("", response_model=SearchResponse)
@handle_airweave_errors
async def search_collections(
    request: SearchRequest,
    client: AirweaveClient = Depends(get_client),
    user: AppUser = Depends(get_user)
):
    """Search across collections and show associated connections."""
    # Verify collection exists
    collection = await client.get_collection(request.collection_id, app_user=user)
    if not collection:
        # Try lowercase
        collection = await client.get_collection(request.collection_id.lower(), app_user=user)
        if not collection:
            raise HTTPException(
                status_code=404,
                detail=f"Collection '{request.collection_id}' not found"
            )
        request.collection_id = collection.readable_id
    

    
    # Perform search
    result = await client.search(
        query=request.query,
        collection_id=request.collection_id,
        limit=request.limit,
        app_user=user
    )
    
    return SearchResponse(
        query=result.query,
        results=result.results,
        total_results=result.total_results,
        collection=result.collection,
    ) 