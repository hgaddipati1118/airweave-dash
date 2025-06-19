"""Azure Storage client with environment-aware configuration."""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, List, Optional

from azure.core.exceptions import ClientAuthenticationError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

from airweave.core.config import settings
from airweave.core.logging import LoggerConfigurator

logger = LoggerConfigurator.configure_logger(__name__, dimensions={"component": "storage_client"})


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    async def list_containers(self) -> List[str]:
        """List all containers/directories."""
        pass

    @abstractmethod
    async def upload_file(self, container_name: str, blob_name: str, data: BinaryIO) -> bool:
        """Upload a file to storage."""
        pass

    @abstractmethod
    async def download_file(self, container_name: str, blob_name: str) -> Optional[bytes]:
        """Download a file from storage."""
        pass

    @abstractmethod
    async def delete_file(self, container_name: str, blob_name: str) -> bool:
        """Delete a file from storage."""
        pass

    @abstractmethod
    async def file_exists(self, container_name: str, blob_name: str) -> bool:
        """Check if a file exists."""
        pass


class AzureStorageBackend(StorageBackend):
    """Azure Blob Storage backend implementation."""

    def __init__(self, blob_service_client: BlobServiceClient):
        """Initialize Azure storage backend.

        Args:
            blob_service_client: Azure BlobServiceClient instance
        """
        self.client = blob_service_client

    async def list_containers(self) -> List[str]:
        """List all containers in the storage account.

        Returns:
            List of container names

        Raises:
            Exception: If listing fails
        """
        try:
            containers = [c.name for c in self.client.list_containers()]
            logger.with_context(containers=containers).info(f"Listed {len(containers)} containers")
            return containers
        except Exception as e:
            logger.error(f"Failed to list containers: {e}")
            raise

    async def upload_file(self, container_name: str, blob_name: str, data: BinaryIO) -> bool:
        """Upload a file to Azure Blob Storage.

        Args:
            container_name: Name of the container
            blob_name: Name of the blob
            data: File data to upload

        Returns:
            True if successful

        Raises:
            Exception: If upload fails
        """
        try:
            container_client = self.client.get_container_client(container_name)
            blob_client = container_client.get_blob_client(blob_name)
            blob_client.upload_blob(data, overwrite=True)
            logger.with_context(
                container=container_name,
                blob=blob_name,
            ).info("Uploaded blob successfully")
            return True
        except Exception as e:
            logger.with_context(
                container=container_name,
                blob=blob_name,
            ).error(f"Failed to upload blob: {e}")
            raise

    async def download_file(self, container_name: str, blob_name: str) -> Optional[bytes]:
        """Download a file from Azure Blob Storage.

        Args:
            container_name: Name of the container
            blob_name: Name of the blob

        Returns:
            File content as bytes, or None if not found

        Raises:
            Exception: If download fails (except for not found)
        """
        try:
            container_client = self.client.get_container_client(container_name)
            blob_client = container_client.get_blob_client(blob_name)
            data = blob_client.download_blob().readall()
            logger.with_context(
                container=container_name,
                blob=blob_name,
                size=len(data),
            ).info("Downloaded blob successfully")
            return data
        except ResourceNotFoundError:
            logger.with_context(container=container_name, blob=blob_name).warning("Blob not found")
            return None
        except Exception as e:
            logger.with_context(
                container=container_name,
                blob=blob_name,
            ).error(f"Failed to download blob: {e}")
            raise

    async def delete_file(self, container_name: str, blob_name: str) -> bool:
        """Delete a file from Azure Blob Storage.

        Args:
            container_name: Name of the container
            blob_name: Name of the blob

        Returns:
            True if successful

        Raises:
            Exception: If deletion fails
        """
        try:
            container_client = self.client.get_container_client(container_name)
            blob_client = container_client.get_blob_client(blob_name)
            blob_client.delete_blob()
            logger.with_context(
                container=container_name,
                blob=blob_name,
            ).info("Deleted blob successfully")
            return True
        except ResourceNotFoundError:
            logger.with_context(container=container_name, blob=blob_name).warning("Blob not found")
            return False
        except Exception as e:
            logger.with_context(
                container=container_name,
                blob=blob_name,
            ).error(f"Failed to delete blob: {e}")
            raise

    async def file_exists(self, container_name: str, blob_name: str) -> bool:
        """Check if a file exists in Azure Blob Storage.

        Args:
            container_name: Name of the container
            blob_name: Name of the blob

        Returns:
            True if the blob exists
        """
        try:
            container_client = self.client.get_container_client(container_name)
            blob_client = container_client.get_blob_client(blob_name)
            return blob_client.exists()
        except Exception as e:
            logger.with_context(
                container=container_name,
                blob=blob_name,
            ).error(f"Failed to check blob existence: {e}")
            return False


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend implementation."""

    def __init__(self, base_path: Path):
        """Initialize local storage backend.

        Args:
            base_path: Base directory for local storage
        """
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def list_containers(self) -> List[str]:
        """List all directories in local storage.

        Returns:
            List of directory names
        """
        try:
            directories = [d.name for d in self.base_path.iterdir() if d.is_dir()]
            logger.with_context(
                directories=directories,
            ).info(f"Listed {len(directories)} local directories")
            return directories
        except Exception as e:
            logger.error(f"Failed to list local directories: {e}")
            raise

    async def upload_file(self, container_name: str, blob_name: str, data: BinaryIO) -> bool:
        """Save a file to local storage.

        Args:
            container_name: Name of the directory
            blob_name: Name of the file
            data: File data to save

        Returns:
            True if successful
        """
        try:
            container_path = self.base_path / container_name
            container_path.mkdir(parents=True, exist_ok=True)

            # Sanitize blob_name to create valid file path
            safe_blob_name = blob_name.replace(":", "_").replace("/", os.sep)
            file_path = container_path / safe_blob_name

            # Ensure parent directories exist
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "wb") as f:
                f.write(data.read())

            logger.with_context(
                container=container_name,
                file=blob_name,
                path=str(file_path),
            ).info("Saved file locally")
            return True
        except Exception as e:
            logger.with_context(
                container=container_name,
                file=blob_name,
            ).error(f"Failed to save file locally: {e}")
            raise

    async def download_file(self, container_name: str, blob_name: str) -> Optional[bytes]:
        """Read a file from local storage.

        Args:
            container_name: Name of the directory
            blob_name: Name of the file

        Returns:
            File content as bytes, or None if not found
        """
        try:
            # Sanitize blob_name to create valid file path
            safe_blob_name = blob_name.replace(":", "_").replace("/", os.sep)
            file_path = self.base_path / container_name / safe_blob_name

            if not file_path.exists():
                logger.with_context(container=container_name, file=blob_name).warning(
                    "File not found"
                )
                return None

            with open(file_path, "rb") as f:
                data = f.read()

            logger.with_context(
                container=container_name,
                file=blob_name,
                size=len(data),
            ).info("Read file from local storage")
            return data
        except Exception as e:
            logger.with_context(
                container=container_name,
                file=blob_name,
            ).error(f"Failed to read local file: {e}")
            raise

    async def delete_file(self, container_name: str, blob_name: str) -> bool:
        """Delete a file from local storage.

        Args:
            container_name: Name of the directory
            blob_name: Name of the file

        Returns:
            True if successful
        """
        try:
            # Sanitize blob_name to create valid file path
            safe_blob_name = blob_name.replace(":", "_").replace("/", os.sep)
            file_path = self.base_path / container_name / safe_blob_name

            if not file_path.exists():
                logger.with_context(container=container_name, file=blob_name).warning(
                    "File not found"
                )
                return False

            file_path.unlink()
            logger.with_context(
                container=container_name,
                file=blob_name,
            ).info("Deleted file from local storage")
            return True
        except Exception as e:
            logger.with_context(
                container=container_name,
                file=blob_name,
            ).error(f"Failed to delete local file: {e}")
            raise

    async def file_exists(self, container_name: str, blob_name: str) -> bool:
        """Check if a file exists in local storage.

        Args:
            container_name: Name of the directory
            blob_name: Name of the file

        Returns:
            True if the file exists
        """
        # Sanitize blob_name to create valid file path
        safe_blob_name = blob_name.replace(":", "_").replace("/", os.sep)
        file_path = self.base_path / container_name / safe_blob_name
        return file_path.exists()


class StorageClient:
    """Environment-aware storage client."""

    def __init__(self, backend: Optional[StorageBackend] = None):
        """Initialize storage client with auto-configuration.

        Args:
            backend: Optional storage backend. If not provided, will be auto-configured.
        """
        self.backend = backend or self._configure_backend()
        self._log_configuration()

    def _configure_backend(self) -> StorageBackend:
        """Configure storage backend based on environment.

        Returns:
            Configured storage backend

        Raises:
            RuntimeError: If configuration fails
        """
        # Prioritize local storage if the skip flag is set
        if os.getenv("SKIP_AZURE_STORAGE", "false").lower() == "true":
            logger.info("SKIP_AZURE_STORAGE is set, using local disk storage")
            local_path = Path("./local_storage")
            self._ensure_default_containers(local_path)
            return LocalStorageBackend(local_path)

        # For non-local environments, Azure is required
        if settings.ENVIRONMENT != "local":
            return self._configure_azure_backend()
        
        # For local environment, try Azure but fall back to local disk
        return self._configure_local_backend()

    def _configure_local_backend(self) -> StorageBackend:
        """Configure backend for local development.

        Tries Azure first, falls back to local disk.

        Returns:
            Configured storage backend
        """
        # Try Azure connection first
        try:
            credential = DefaultAzureCredential()
            storage_account = os.getenv(
                "AZURE_STORAGE_ACCOUNT_NAME", self._get_default_storage_account()
            )

            if not storage_account:
                raise ValueError("No storage account name available")

            blob_client = BlobServiceClient(
                account_url=f"https://{storage_account}.blob.core.windows.net",
                credential=credential,
            )

            # Test connection
            try:
                # Just try to get the first container to test connection
                next(iter(blob_client.list_containers()), None)
            except Exception:
                # If we can't list containers, connection has failed
                raise

            logger.with_context(
                storage_account=storage_account,
            ).info("Connected to Azure Storage via Azure CLI")
            return AzureStorageBackend(blob_client)

        except (ClientAuthenticationError, Exception) as e:
            logger.warning(
                f"Azure connection failed, using local disk: {e} (error type: {type(e).__name__})"
            )

            # Fall back to local disk
            local_path = Path("./local_storage")
            self._ensure_default_containers(local_path)
            return LocalStorageBackend(local_path)

    def _configure_azure_backend(self) -> StorageBackend:
        """Configure Azure backend for dev/prod environments.

        Returns:
            Configured Azure storage backend

        Raises:
            RuntimeError: If Azure connection fails
        """
        try:
            credential = DefaultAzureCredential()
            storage_account = os.getenv(
                "AZURE_STORAGE_ACCOUNT_NAME", self._get_default_storage_account()
            )

            if not storage_account:
                raise ValueError("No storage account name configured")

            blob_client = BlobServiceClient(
                account_url=f"https://{storage_account}.blob.core.windows.net",
                credential=credential,
            )

            # Test connection
            try:
                # Just try to get the first container to test connection
                next(iter(blob_client.list_containers()), None)
            except Exception:
                # If we can't list containers, connection has failed
                raise

            logger.with_context(
                environment=settings.ENVIRONMENT,
                storage_account=storage_account,
            ).info("Connected to Azure Storage using managed identity")
            return AzureStorageBackend(blob_client)

        except Exception as e:
            logger.with_context(
                environment=settings.ENVIRONMENT,
                error_type=type(e).__name__,
            ).error(f"Failed to connect to Azure Storage: {e}")
            raise RuntimeError(f"Azure Storage connection failed: {e}") from e

    def _get_default_storage_account(self) -> str:
        """Get default storage account name based on environment.

        Returns:
            Storage account name
        """
        env_map = {
            "local": "airweavecoredevstorage",  # Use dev storage when running locally
            "dev": "airweavecoredevstorage",
            "prd": "airweavecoreprdsstorage",
        }
        return env_map.get(settings.ENVIRONMENT, "")

    def _ensure_default_containers(self, base_path: Path) -> None:
        """Ensure default containers exist for local storage.

        Args:
            base_path: Base directory for local storage
        """
        default_containers = ["sync-data", "sync-metadata", "processed-files", "backup"]
        for container in default_containers:
            (base_path / container).mkdir(parents=True, exist_ok=True)

    def _log_configuration(self) -> None:
        """Log the current storage configuration."""
        backend_type = type(self.backend).__name__
        logger.with_context(
            environment=settings.ENVIRONMENT,
            backend_type=backend_type,
            is_local_disk=isinstance(self.backend, LocalStorageBackend),
        ).info("Storage client configured")

    @property
    def is_local_disk(self) -> bool:
        """Check if using local disk storage.

        Returns:
            True if using local disk storage
        """
        return isinstance(self.backend, LocalStorageBackend)

    # Delegate all storage operations to the backend
    async def list_containers(self) -> List[str]:
        """List all containers/directories."""
        return await self.backend.list_containers()

    async def upload_file(self, container_name: str, blob_name: str, data: BinaryIO) -> bool:
        """Upload a file to storage."""
        return await self.backend.upload_file(container_name, blob_name, data)

    async def download_file(self, container_name: str, blob_name: str) -> Optional[bytes]:
        """Download a file from storage."""
        return await self.backend.download_file(container_name, blob_name)

    async def delete_file(self, container_name: str, blob_name: str) -> bool:
        """Delete a file from storage."""
        return await self.backend.delete_file(container_name, blob_name)

    async def file_exists(self, container_name: str, blob_name: str) -> bool:
        """Check if a file exists."""
        return await self.backend.file_exists(container_name, blob_name)
