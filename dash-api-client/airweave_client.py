"""
Airweave HTTP Client

A clean, well-structured client library for making HTTP requests to the Airweave backend API.
This library provides a simple interface for managing collections, connections, and sync operations.
"""

import httpx
import re
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel
from datetime import datetime
from enum import Enum
from uuid import UUID
from httpx import AsyncClient

from models import (
    AppUser,
    Collection,
    Connection,
    SearchResult,
    SourceConnection,
    SyncJob,
    SourceType,
    AirweaveConfig,
    ConnectionConfig,
    ClientCollection,
    ClientConnection,
    ClientSyncJob,
    ClientSearchResult,
)

# Make all classes available at module level for easy importing
__all__ = [
    "AirweaveClient", "AirweaveConfig", "AppUser", "ConnectionConfig", 
    "Collection", "Connection", "SyncJob", "SearchResult", "SourceConnection",
    "ClientCollection", "ClientConnection", "ClientSyncJob", "ClientSearchResult",
    "SourceType", "AirweaveError", "NotFoundError"
]


# Custom Exceptions
class AirweaveError(Exception):
    """Base exception for Airweave client errors."""
    pass


class NotFoundError(AirweaveError):
    """Exception raised when a resource is not found."""
    pass


class AirweaveClient:
    """
    HTTP client for the Airweave backend API.
    
    Provides methods for managing:
    - Collections: Create, read, update, delete collections
    - Connections: Manage source connections and configurations
    - Sync Operations: Trigger and monitor data synchronization
    - Search: Query data within collections
    """
    
    def __init__(self, config: AirweaveConfig):
        """Initialize the Airweave client with configuration."""
        self.config = config
        self.base_url = config.base_url.rstrip('/')
        
        self.client = httpx.AsyncClient(
            timeout=config.timeout,
            headers={"Content-Type": "application/json"},
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()
    
    # ============================================================================
    # PRIVATE HELPER METHODS
    # ============================================================================
    
    def _get_headers(self, app_user: Optional[AppUser] = None) -> Dict[str, str]:
        """Get headers including user context if provided."""
        headers = {"Content-Type": "application/json"}
        
        if app_user:
            headers.update({
                "X-User-ID": app_user.user_id,
                "X-User-Email": app_user.email,
                "X-User-Name": app_user.name or app_user.user_id
            })
        return headers
    
    def _get_url(self, path: str) -> str:
        """Get the full URL for a path, ensuring consistent trailing slashes."""
        path = path.strip('/')
        return f"{self.base_url}/{path}/"
    
    def _format_readable_id(self, name: str) -> str:
        """
        Format a name into a valid readable_id.
        
        Rules:
        1. Convert to lowercase
        2. Replace non-alphanumeric chars with hyphens
        3. Ensure no consecutive hyphens
        4. Trim hyphens from start/end
        """
        readable_id = re.sub(r'[^a-z0-9]+', '-', name.lower().strip())
        readable_id = re.sub(r'-+', '-', readable_id)
        readable_id = readable_id.strip('-')
        return readable_id or 'collection'
    
    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Handle HTTP response and raise appropriate exceptions."""
        if response.status_code == 404:
            raise NotFoundError(f"Resource not found: {response.text}")
        elif response.status_code >= 400:
            raise AirweaveError(f"API error {response.status_code}: {response.text}")
        
        try:
            return response.json()
        except Exception:
            return {"message": response.text}
    
    def _parse_datetime(self, datetime_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string from API response."""
        if not datetime_str:
            return None
        return datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
    
    async def _make_request(
        self, 
        method: str, 
        path: str, 
        app_user: Optional[AppUser] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Make an HTTP request with consistent error handling."""
        try:
            response = await self.client.request(
                method=method,
                url=self._get_url(path),
                headers=self._get_headers(app_user),
                **kwargs
            )
            return self._handle_response(response)
        except httpx.TimeoutException:
            raise AirweaveError(f"Timeout while making {method} request to {path}")
        except Exception as e:
            if isinstance(e, (AirweaveError, NotFoundError)):
                raise
            raise AirweaveError(f"Error making {method} request to {path}: {str(e)}")
    
    # ============================================================================
    # COLLECTION MANAGEMENT
    # ============================================================================
    
    async def create_collection(
        self, 
        name: str, 
        description: Optional[str] = None, 
        custom_id: Optional[str] = None,
        app_user: Optional[AppUser] = None
    ) -> ClientCollection:
        """Create a new collection."""
        data = {
            "name": name,
            "readable_id": self._format_readable_id(custom_id or name)
        }
        if description:
            data["description"] = description
            
        result = await self._make_request("POST", "collections", app_user, json=data)
        return ClientCollection(**result)
    
    async def get_collections(self, app_user: Optional[AppUser] = None) -> List[ClientCollection]:
        """Get all collections."""
        result = await self._make_request("GET", "collections", app_user)
        return [ClientCollection(**item) for item in result]
    
    async def get_collection(self, collection_id: str, app_user: Optional[AppUser] = None) -> Optional[ClientCollection]:
        """Get a specific collection by ID."""
        try:
            result = await self._make_request("GET", f"collections/{collection_id}", app_user)
            return ClientCollection(**result)
        except NotFoundError:
            return None
    
    async def delete_collection(self, collection_id: str, app_user: Optional[AppUser] = None) -> bool:
        """Delete a collection."""
        try:
            await self._make_request("DELETE", f"collections/{collection_id}", app_user)
            return True
        except Exception:
            return False
    
    # ============================================================================
    # CONNECTION MANAGEMENT
    # ============================================================================
    
    async def create_connection(self, config: ConnectionConfig, app_user: Optional[AppUser] = None) -> ClientConnection:
        """Create a new source connection."""
        # Ensure the collection exists or create it
        collection_id = self._format_readable_id(config.collection_id)
        collection = await self.get_collection(collection_id, app_user)
        if not collection:
            collection = await self.create_collection(
                name=config.name,
                description=f"Auto-created collection for {config.name}",
                custom_id=collection_id,
                app_user=app_user
            )

        # Create the source connection
        data = {
            "name": config.name,
            "short_name": config.source_type.value,
            "collection": collection.readable_id,
            "auth_fields": config.auth_fields,
            "config_fields": config.config_fields,
            "sync_immediately": True
        }
        
        result = await self._make_request("POST", "source-connections", app_user, json=data)
        
        return ClientConnection(
            id=result["id"],
            name=result["name"],
            short_name=result.get("short_name", config.source_type.value),
            collection_id=result.get("collection", collection.readable_id),
            status=result.get("status", "in_progress"),
            created_at=self._parse_datetime(result.get("created_at"))
        )
    
    async def get_connections(self, collection_id: Optional[str] = None, app_user: Optional[AppUser] = None) -> List[ClientConnection]:
        """Get all connections, optionally filtered by collection ID."""
        params = {"collection": collection_id} if collection_id else {}
        result = await self._make_request("GET", "source-connections", app_user, params=params)
        
        return [
            ClientConnection(
                id=item["id"],
                name=item["name"],
                short_name=item.get("short_name", "unknown"),
                collection_id=item.get("collection", "unknown"),
                status=item.get("status", "active"),
                created_at=self._parse_datetime(item.get("created_at"))
            )
            for item in result
        ]
    
    async def get_connection(self, connection_id: str, app_user: Optional[AppUser] = None) -> Optional[ClientConnection]:
        """Get a specific connection by ID."""
        try:
            result = await self._make_request("GET", f"source-connections/{connection_id}", app_user)
            
            return ClientConnection(
                id=result["id"],
                name=result["name"],
                short_name=result.get("short_name", "unknown"),
                collection_id=result.get("collection", "unknown"),
                status=result.get("status", "active"),
                created_at=self._parse_datetime(result.get("created_at"))
            )
        except NotFoundError:
            return None
    
    async def delete_connection(self, connection_id: str, app_user: Optional[AppUser] = None) -> bool:
        """Delete a connection."""
        try:
            await self._make_request("DELETE", f"source-connections/{connection_id}", app_user)
            return True
        except Exception:
            return False
    
    # ============================================================================
    # SYNC OPERATIONS
    # ============================================================================
    
    async def sync_connection(
        self, 
        connection_id: str, 
        access_token: Optional[str] = None, 
        app_user: Optional[AppUser] = None
    ) -> ClientSyncJob:
        """
        Trigger a sync for a connection.
        
        Args:
            connection_id: The ID of the connection to sync
            access_token: Optional direct access token to use instead of stored credentials
            app_user: The application user context
            
        Returns:
            SyncJob: The created sync job
        """
        data = {"access_token": access_token} if access_token else None
        
        try:
            kwargs = {"json": data} if data else {}
            result = await self._make_request("POST", f"source-connections/{connection_id}/run", app_user, **kwargs)
            
            return ClientSyncJob(
                id=result["id"],
                connection_id=connection_id,
                status=result.get("status", "pending"),
                created_at=self._parse_datetime(result.get("created_at")),
                completed_at=self._parse_datetime(result.get("completed_at")),
                error_message=result.get("error")
            )
        except NotFoundError:
            raise AirweaveError(f"Source connection {connection_id} not found")
    
    async def get_latest_sync_status(self, connection_id: str, app_user: Optional[AppUser] = None) -> Optional[ClientSyncJob]:
        """Get the latest sync status for a connection."""
        try:
            # Use the source connection jobs endpoint which gives us the jobs for this specific connection
            jobs = await self._make_request("GET", f"source-connections/{connection_id}/jobs", app_user)
            if not jobs:
                return None
                
            # Get the most recent job (first in list, assuming backend sorts by date DESC)
            latest_job = jobs[0] if jobs else None
            if not latest_job:
                return None
                
            return ClientSyncJob(
                id=latest_job["id"],
                connection_id=connection_id,
                status=latest_job.get("status", "unknown"),
                created_at=self._parse_datetime(latest_job.get("created_at")),
                completed_at=self._parse_datetime(latest_job.get("completed_at")),
                error_message=latest_job.get("error_message")
            )
        except NotFoundError:
            return None
    

    
    # ============================================================================
    # SEARCH OPERATIONS
    # ============================================================================
    
    async def search(
        self, 
        query: str, 
        collection_id: str, 
        limit: int = 10, 
        app_user: Optional[AppUser] = None
    ) -> ClientSearchResult:
        """Search within a collection."""
        params = {"query": query, "limit": limit}
        result = await self._make_request("GET", f"collections/{collection_id}/search", app_user, params=params)
        
        return ClientSearchResult(
            query=query,
            results=result.get("results", []),
            total_results=len(result.get("results", [])),  # Calculate from results since backend doesn't provide it
            collection=collection_id
        )
    
 