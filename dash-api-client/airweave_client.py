"""
Airweave HTTP Client

A client library for making HTTP requests to the Airweave backend API.
This replaces the non-existent airweave_client import with actual HTTP calls.
"""

import httpx
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
from datetime import datetime
from enum import Enum
import re
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
    "SourceType", "ScheduleType", "ScheduleConfig", "AirweaveScheduler",
    "AirweaveError", "NotFoundError"
]


class AirweaveError(Exception):
    """Base exception for Airweave client errors."""
    pass


class NotFoundError(AirweaveError):
    """Exception raised when a resource is not found."""
    pass


class AirweaveClient:
    """HTTP client for the Airweave backend API."""
    
    def __init__(self, config: AirweaveConfig):
        self.config = config
        self.base_url = config.base_url.rstrip('/')
        
        # Set default headers
        headers = {"Content-Type": "application/json"}
            
        self.client = httpx.AsyncClient(
            timeout=config.timeout,
            headers=headers,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
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
    
    def _get_url(self, path: str) -> str:
        """Get the full URL for a path, ensuring consistent trailing slashes."""
        path = path.strip('/')
        return f"{self.base_url}/{path}/"
    
    def _format_readable_id(self, name: str) -> str:
        """Format a name into a valid readable_id.
        
        Rules:
        1. Convert to lowercase
        2. Replace non-alphanumeric chars with hyphens
        3. Ensure no consecutive hyphens
        4. Trim hyphens from start/end
        """
        # Convert to lowercase and replace non-alphanumeric chars with hyphens
        readable_id = re.sub(r'[^a-z0-9]+', '-', name.lower().strip())
        # Ensure no consecutive hyphens
        readable_id = re.sub(r'-+', '-', readable_id)
        # Trim hyphens from start and end
        readable_id = readable_id.strip('-')
        # If empty after cleaning, use a default
        if not readable_id:
            readable_id = 'collection'
        return readable_id
    
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
            
        response = await self.client.post(
            self._get_url("collections"), 
            json=data,
            headers=self._get_headers(app_user)
        )
        result = self._handle_response(response)
        return ClientCollection(**result)
    
    async def get_collections(self, app_user: Optional[AppUser] = None) -> List[ClientCollection]:
        """Get all collections."""
        response = await self.client.get(
            self._get_url("collections"),
            headers=self._get_headers(app_user)
        )
        result = self._handle_response(response)
        return [ClientCollection(**item) for item in result]
    
    async def get_collection(self, collection_id: str, app_user: Optional[AppUser] = None) -> Optional[ClientCollection]:
        """Get a specific collection by ID."""
        try:
            response = await self.client.get(
                self._get_url(f"collections/{collection_id}"),
                headers=self._get_headers(app_user)
            )
            result = self._handle_response(response)
            return ClientCollection(**result)
        except NotFoundError:
            return None
    
    async def delete_collection(self, collection_id: str, app_user: Optional[AppUser] = None) -> bool:
        """Delete a collection."""
        try:
            response = await self.client.delete(
                self._get_url(f"collections/{collection_id}"),
                headers=self._get_headers(app_user)
            )
            self._handle_response(response)
            return True
        except Exception:
            return False
    
    async def create_connection(self, config: ConnectionConfig, app_user: Optional[AppUser] = None) -> ClientConnection:
        """Create a new source connection."""
        # First, ensure the collection exists or create it
        collection_id = self._format_readable_id(config.collection_id)
        collection = await self.get_collection(collection_id, app_user)
        if not collection:
            # Create the collection if it doesn't exist
            collection = await self.create_collection(
                name=config.name,
                description=f"Auto-created collection for {config.name}",
                custom_id=collection_id,
                app_user=app_user
            )
    

        # Create the source connection
        data = {
            "name": config.name,
            "short_name": config.source_type.value,  # Backend expects short_name
            "collection": collection.readable_id,     # Backend expects collection
            "auth_fields": config.auth_fields,       # Auth fields for the source
            "config_fields": config.config_fields,   # Config fields for the source
            "sync_immediately": True                 # Start sync immediately
        }
        
        try:
            response = await self.client.post(
                self._get_url("source-connections"), 
                json=data,
                headers=self._get_headers(app_user),
                timeout=self.config.timeout
            )
            result = self._handle_response(response)
            
            # Convert to our Connection model format
            return ClientConnection(
                id=result["id"],
                name=result["name"],
                short_name=result.get("source_type", config.source_type.value),
                collection_id=collection.readable_id,
                status=result.get("status", "in_progress"),
                created_at=datetime.fromisoformat(result["created_at"].replace("Z", "+00:00")) if result.get("created_at") else None
            )
        except httpx.TimeoutException:
            raise AirweaveError(f"Timeout while creating {config.source_type.value} connection. Please try again.")
        except Exception as e:
            raise AirweaveError(f"Error creating {config.source_type.value} connection: {str(e)}")
    
    async def get_connections(self, collection_id: Optional[str] = None, app_user: Optional[AppUser] = None) -> List[ClientConnection]:
        """Get all connections, optionally filtered by collection ID."""
        # Build query parameters
        params = {}
        if collection_id:
            params["collection"] = collection_id
        
        response = await self.client.get(
            self._get_url("source-connections"),
            params=params,
            headers=self._get_headers(app_user)
        )
        result = self._handle_response(response)
        
        connections = []
        for item in result:
            connections.append(ClientConnection(
                id=item["id"],
                name=item["name"],
                short_name=item.get("short_name", "unknown"),
                collection_id=item.get("collection", "unknown"),
                status=item.get("status", "active"),
                created_at=datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")) if item.get("created_at") else None
            ))
        return connections
    
    async def get_connection(self, connection_id: str, app_user: Optional[AppUser] = None) -> Optional[ClientConnection]:
        """Get a specific connection by ID."""
        try:
            response = await self.client.get(
                self._get_url(f"source-connections/{connection_id}"),
                headers=self._get_headers(app_user)
            )
            result = self._handle_response(response)
            
            return ClientConnection(
                id=result["id"],
                name=result["name"],
                short_name=result.get("short_name", "unknown"),
                collection_id=result.get("collection", "unknown"),
                status=result.get("status", "active"),
                created_at=datetime.fromisoformat(result["created_at"].replace("Z", "+00:00")) if result.get("created_at") else None
            )
        except NotFoundError:
            return None
    
    async def delete_connection(self, connection_id: str, app_user: Optional[AppUser] = None) -> bool:
        """Delete a connection."""
        try:
            response = await self.client.delete(
                self._get_url(f"source-connections/{connection_id}"),
                headers=self._get_headers(app_user)
            )
            self._handle_response(response)
            return True
        except Exception:
            return False
    
    async def sync_connection(self, connection_id: str, access_token: Optional[str] = None, app_user: Optional[AppUser] = None) -> ClientSyncJob:
        """Trigger a sync for a connection.
        
        Args:
            connection_id: The ID of the connection to sync
            access_token: Optional direct access token to use instead of stored credentials.
                         Only needed for OAuth 2.0 sources when you want to use a new access token
                         instead of having Airweave refresh the stored token.
            app_user: The application user context
            
        Returns:
            SyncJob: The created sync job
            
        Raises:
            AirweaveError: If the connection doesn't exist or sync creation fails
        """
        # Build request data
        data = {}
        if access_token:
            data["access_token"] = access_token
            
        try:
            response = await self.client.post(
                self._get_url(f"source-connections/{connection_id}/run/"),
                json=data,
                headers=self._get_headers(app_user)
            )
            result = self._handle_response(response)
            
            return ClientSyncJob(
                id=result["id"],
                connection_id=connection_id,
                status=result.get("status", "pending"),
                created_at=datetime.fromisoformat(result["created_at"].replace("Z", "+00:00")) if result.get("created_at") else None,
                completed_at=datetime.fromisoformat(result["completed_at"].replace("Z", "+00:00")) if result.get("completed_at") else None,
                error_message=result.get("error")
            )
        except NotFoundError:
            raise AirweaveError(f"Source connection {connection_id} not found")
        except Exception as e:
            raise AirweaveError(f"Failed to trigger sync: {str(e)}")
    
    async def get_sync_job(self, sync_id: str, connection_id: str, app_user: Optional[AppUser] = None) -> Optional[ClientSyncJob]:
        """Get sync job status.
        
        Args:
            sync_id: The ID of the sync job
            connection_id: The ID of the source connection
            app_user: The application user context
            
        Returns:
            ClientSyncJob if found, None if not found
            
        Raises:
            AirweaveError: If there is an error fetching the job status
        """
        try:
            response = await self.client.get(
                self._get_url(f"source-connections/{connection_id}/jobs/{sync_id}/"),
                headers=self._get_headers(app_user)
            )
            result = self._handle_response(response)
            
            if not result:
                return None
                
            return ClientSyncJob(
                id=result["id"],
                connection_id=connection_id,
                status=result.get("status", "unknown"),
                created_at=datetime.fromisoformat(result["created_at"].replace("Z", "+00:00")) if result.get("created_at") else None,
                completed_at=datetime.fromisoformat(result["completed_at"].replace("Z", "+00:00")) if result.get("completed_at") else None,
                error_message=result.get("error")
            )
        except NotFoundError:
            return None
        except Exception as e:
            raise AirweaveError(f"Failed to get sync job status: {str(e)}")
    
    async def search(
        self, 
        query: str, 
        collection_id: str, 
        limit: int = 10, 
        app_user: Optional[AppUser] = None
    ) -> ClientSearchResult:
        """Search within a collection."""
        params = {"query": query, "limit": limit}
        response = await self.client.get(
            self._get_url(f"collections/{collection_id}/search"), 
            params=params,
            headers=self._get_headers(app_user)
        )
        result = self._handle_response(response)
        
        return ClientSearchResult(
            query=query,
            results=result.get("results", []),
            total_results=result.get("total_results", 0),
            collection=collection_id
        )

    async def list_source_connections(self, app_user: Optional[AppUser] = None) -> List[SourceConnection]:
        """List all source connections."""
        response = await self.client.get(
            self._get_url("source-connections/"),  # Added trailing slash
            headers=self._get_headers(app_user)
        )
        results = self._handle_response(response)
        return [SourceConnection(**result) for result in results]

    async def create_source_connection(
        self,
        source_type: str,
        name: str,
        credentials: Dict[str, Any],
        app_user: Optional[AppUser] = None
    ) -> SourceConnection:
        """Create a new source connection."""
        data = {
            "source_type": source_type,
            "name": name,
            "credentials": credentials
        }
        response = await self.client.post(
            self._get_url("source-connections/"),  # Added trailing slash
            json=data,
            headers=self._get_headers(app_user)
        )
        result = self._handle_response(response)
        return SourceConnection(**result)

    async def get_source_connection(self, connection_id: str, app_user: Optional[AppUser] = None) -> SourceConnection:
        """Get a source connection by ID."""
        response = await self.client.get(
            self._get_url(f"source-connections/{connection_id}/"),  # Added trailing slash
            headers=self._get_headers(app_user)
        )
        result = self._handle_response(response)
        return SourceConnection(**result)

    async def delete_source_connection(self, connection_id: str, app_user: Optional[AppUser] = None) -> None:
        """Delete a source connection."""
        response = await self.client.delete(
            self._get_url(f"source-connections/{connection_id}/"),  # Added trailing slash
            headers=self._get_headers(app_user)
        )
        self._handle_response(response)

    async def get_latest_sync(self, connection_id: str, app_user: Optional[AppUser] = None) -> Optional[ClientSyncJob]:
        """Get the latest sync for a connection.
        
        Args:
            connection_id: The ID of the connection to get the latest sync for
            app_user: The application user context
            
        Returns:
            ClientSyncJob: The latest sync job if found, None otherwise
        """
        try:
            response = await self.client.get(
                self._get_url(f"sync/latest"),
                params={"connection_id": connection_id},
                headers=self._get_headers(app_user)
            )
            result = self._handle_response(response)
            
            if not result:
                return None
                
            return ClientSyncJob(
                id=result["id"],
                connection_id=connection_id,
                status=result.get("status", "unknown"),
                created_at=datetime.fromisoformat(result["created_at"].replace("Z", "+00:00")) if result.get("created_at") else None,
                completed_at=datetime.fromisoformat(result["completed_at"].replace("Z", "+00:00")) if result.get("completed_at") else None,
                error_message=result.get("error_message")
            )
        except NotFoundError:
            return None
            
    async def get_latest_sync_status(self, connection_id: str, app_user: Optional[AppUser] = None) -> Optional[ClientSyncJob]:
        """Get the latest sync status for a connection, including job details.
        
        This method:
        1. Gets the latest sync for the connection
        2. Gets the detailed status for that sync
        
        Args:
            connection_id: The ID of the connection to get the latest sync status for
            app_user: The application user context
            
        Returns:
            ClientSyncJob: The latest sync job with status details if found, None otherwise
        """
        # Get the latest sync
        latest_sync = await self.get_latest_sync(connection_id, app_user)
        if not latest_sync:
            return None
            
        # Get the detailed status
        return await self.get_sync_job(latest_sync.id, connection_id, app_user)


# Optional scheduler classes (not implemented for now)
class ScheduleType(str, Enum):
    """Schedule types."""
    INTERVAL = "interval"
    CRON = "cron"


class ScheduleConfig(BaseModel):
    """Schedule configuration."""
    schedule_type: ScheduleType
    interval_seconds: Optional[int] = None
    cron_expression: Optional[str] = None


class AirweaveScheduler:
    """Placeholder scheduler class."""
    
    def __init__(self, client: AirweaveClient):
        self.client = client
        self._running = False
    
    def start(self):
        """Start the scheduler."""
        self._running = True
    
    def stop(self):
        """Stop the scheduler."""
        self._running = False 