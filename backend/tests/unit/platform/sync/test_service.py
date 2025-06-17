"""Unit tests for the SyncService class."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.db.unit_of_work import UnitOfWork
from airweave.core.sync_service import SyncService, sync_service


@pytest.fixture
def mock_uow():
    """Create a mock unit of work."""
    mock = MagicMock(spec=UnitOfWork)
    mock.session = AsyncMock(spec=AsyncSession)
    return mock


@pytest.fixture
def mock_collection():
    """Create a mock collection."""
    return MagicMock(spec=schemas.Collection)


@pytest.fixture
def mock_source_connection():
    """Create a mock source connection."""
    return MagicMock(spec=schemas.Connection)


class TestSyncServiceCreate:
    """Tests for the SyncService.create method."""

    @pytest.mark.asyncio
    async def test_create_success(self, mock_db, mock_user, mock_uow):
        """Test successful sync creation."""
        # Arrange
        sync_id = uuid.uuid4()

        # Mock crud.sync.create
        with patch("airweave.crud.sync.create") as mock_create:
            mock_sync = MagicMock(spec=schemas.Sync)
            mock_sync.id = sync_id
            mock_create.return_value = mock_sync

            # Mock dag_service.create_initial_dag
            with patch(
                "airweave.core.dag_service.dag_service.create_initial_dag"
            ) as mock_create_dag:
                mock_create_dag.return_value = MagicMock(spec=schemas.SyncDag)

                # Create sync input
                sync_create = schemas.SyncCreate(
                    name="Test Sync",
                    description="Test description",
                    source_connection_id=uuid.uuid4(),
                    destination_connection_ids=[uuid.uuid4()],
                )

                # Act
                service = SyncService()
                result = await service.create(
                    db=mock_db,
                    sync=sync_create,
                    current_user=mock_user,
                    uow=mock_uow,
                )

                # Assert
                mock_create.assert_called_once_with(
                    db=mock_db,
                    obj_in=sync_create,
                    current_user=mock_user,
                    uow=mock_uow,
                )
                mock_uow.session.flush.assert_called_once()
                mock_create_dag.assert_called_once_with(
                    db=mock_db,
                    sync_id=sync_id,
                    current_user=mock_user,
                    uow=mock_uow,
                )
                assert result == mock_sync


class TestSyncServiceRun:
    """Tests for the SyncService.run method."""

    @pytest.mark.asyncio
    async def test_run_success(self, mock_sync, mock_sync_job, mock_sync_dag, mock_user, mock_collection, mock_source_connection):
        """Test successful sync run."""
        # Arrange
        mock_db_context = AsyncMock()
        mock_db = AsyncMock(spec=AsyncSession)
        mock_db_context.__aenter__.return_value = mock_db

        mock_orchestrator = AsyncMock()
        mock_sync_result = MagicMock(spec=schemas.Sync)
        mock_orchestrator.run.return_value = mock_sync_result

        # Mock get_db_context
        with patch("airweave.core.sync_service.get_db_context") as mock_get_db_context:
            mock_get_db_context.return_value = mock_db_context

            # Mock SyncFactory.create_orchestrator
            with patch(
                "airweave.core.sync_service.SyncFactory.create_orchestrator"
            ) as mock_create_orchestrator:
                mock_create_orchestrator.return_value = mock_orchestrator

                # Act
                service = SyncService()
                result = await service.run(
                    sync=mock_sync,
                    sync_job=mock_sync_job,
                    dag=mock_sync_dag,
                    collection=mock_collection,
                    source_connection=mock_source_connection,
                    current_user=mock_user,
                )

                # Assert
                mock_get_db_context.assert_called_once()
                mock_create_orchestrator.assert_called_once_with(
                    db=mock_db,
                    sync=mock_sync,
                    sync_job=mock_sync_job,
                    dag=mock_sync_dag,
                    collection=mock_collection,
                    source_connection=mock_source_connection,
                    current_user=mock_user,
                    access_token=None,
                )
                mock_orchestrator.run.assert_called_once()
                assert result == mock_sync_result

    @pytest.mark.asyncio
    async def test_run_error_handling(self, mock_sync, mock_sync_job, mock_sync_dag, mock_user, mock_collection, mock_source_connection):
        """Test error handling during sync run."""
        # Arrange
        mock_db_context = AsyncMock()
        mock_db = AsyncMock(spec=AsyncSession)
        mock_db_context.__aenter__.return_value = mock_db
        test_error = Exception("Test error")

        # Mock get_db_context
        with patch("airweave.core.sync_service.get_db_context") as mock_get_db_context:
            mock_get_db_context.return_value = mock_db_context

            # Mock SyncFactory.create_orchestrator to raise an exception
            with patch(
                "airweave.core.sync_service.SyncFactory.create_orchestrator"
            ) as mock_create_orchestrator:
                mock_create_orchestrator.side_effect = test_error

                # Mock logger.error
                with patch("airweave.core.sync_service.logger.error") as mock_logger_error:
                    # Act & Assert
                    with patch("airweave.core.sync_service.sync_job_service.update_status") as mock_update_status:
                        mock_update_status.return_value = None
                        service = SyncService()
                        with pytest.raises(Exception) as excinfo:
                            await service.run(
                                sync=mock_sync,
                                sync_job=mock_sync_job,
                                dag=mock_sync_dag,
                                collection=mock_collection,
                                source_connection=mock_source_connection,
                                current_user=mock_user,
                            )

                    # Verify the exception was logged and re-raised
                    assert excinfo.value == test_error
                    mock_logger_error.assert_called_once()
                    assert "Error during sync" in mock_logger_error.call_args[0][0]


class TestSyncServiceSingleton:
    """Tests for the SyncService singleton instance."""

    def test_singleton_instance(self):
        """Test that sync_service is an instance of SyncService."""
        assert isinstance(sync_service, SyncService)
