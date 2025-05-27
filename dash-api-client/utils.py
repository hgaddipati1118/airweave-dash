"""Utility functions for the Airweave Client API."""

import logging
from typing import Callable, TypeVar, Any, Optional
from functools import wraps

from fastapi import HTTPException
from airweave_client import AirweaveError, NotFoundError

from models import CollectionResponse, ConnectionResponse


logger = logging.getLogger(__name__)

T = TypeVar('T')


def handle_airweave_errors(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to handle Airweave client errors."""
    @wraps(func)
    async def wrapper(*args, **kwargs) -> T:
        try:
            return await func(*args, **kwargs)
        except NotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except AirweaveError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")
    return wrapper


def to_collection_response(collection: Optional[Any]) -> Optional[CollectionResponse]:
    """Convert collection object to response model."""
    if collection is None:
        return None
        
    return CollectionResponse(
        id=collection.id,
        readable_id=collection.readable_id,
        name=collection.name,
        description=collection.description,
        created_at=collection.created_at.isoformat() if collection.created_at else None
    )


def to_connection_response(connection: Any) -> ConnectionResponse:
    """Convert connection object to response model."""
    return ConnectionResponse(
        id=connection.id,
        name=connection.name,
        source_type=connection.short_name,
        collection_name=connection.collection_id,
        status=connection.status,
        created_at=connection.created_at.isoformat() if connection.created_at else None
    )


def setup_logging() -> None:
    """Configure application logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ) 