"""FastAPI dependencies for the Airweave Client API."""

from typing import Optional
from fastapi import HTTPException, Header

from airweave_client import AirweaveClient, AppUser


# Global state - will be set by main.py
_client: Optional[AirweaveClient] = None
_default_user: Optional[AppUser] = None


def set_global_client(client: AirweaveClient) -> None:
    """Set the global client instance."""
    global _client
    _client = client


def set_default_user(user: AppUser) -> None:
    """Set the default user instance."""
    global _default_user
    _default_user = user


def get_client() -> AirweaveClient:
    """Get the Airweave client instance."""
    if _client is None:
        raise HTTPException(status_code=500, detail="Airweave client not initialized")
    return _client


def get_user(
    x_user_id: Optional[str] = Header(None),
    x_user_email: Optional[str] = Header(None),
    x_user_name: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
) -> AppUser:
    """Get user context from request headers or fall back to default user."""
    if x_user_id and x_user_email:
        return AppUser(
            user_id=x_user_id,
            email=x_user_email,
            name=x_user_name or x_user_id,
            metadata={"source": "header"}
        )
    
    if _default_user is None:
        raise HTTPException(status_code=500, detail="Default user not initialized")
    return _default_user 