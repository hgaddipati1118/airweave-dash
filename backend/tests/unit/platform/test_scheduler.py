"""Unit tests for the scheduler module."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from airweave import crud, schemas
from airweave.core.shared_models import SyncJobStatus, SyncStatus
from airweave.platform.scheduler import PlatformScheduler, ensure_utc


@pytest.fixture
def mock_sync_with_schedule(mock_user):
    """Create a mock sync with a cron schedule."""
    organization_id = uuid.uuid4()
    return schemas.Sync(
        id=uuid.uuid4(),
        name="Test Sync With Schedule",
        description="Test description with schedule",
        source_connection_id=uuid.uuid4(),
        destination_connection_ids=[uuid.uuid4()],
        user_id=mock_user.id,
        tenant_id=uuid.uuid4(),
        created_at="2023-01-01T00:00:00",
        updated_at="2023-01-01T00:00:00",
        organization_id=organization_id,
        status=SyncStatus.ACTIVE,
        cron_schedule="0 0 * * *",  # Daily at midnight
        next_scheduled_run=datetime.now(timezone.utc),
        modified_at="2023-01-01T00:00:00",
        created_by_email=mock_user.email,
        modified_by_email=mock_user.email,
    )


@pytest.fixture
def mock_sync_multiple():
    """Create multiple mock syncs with different schedules."""
    organization_id = uuid.uuid4()
    base_time = datetime.now(timezone.utc)

    # Sync that is due (next_scheduled_run in the past)
    due_sync = schemas.Sync(
        id=uuid.uuid4(),
        name="Due Sync",
        description="Due sync description",
        source_connection_id=uuid.uuid4(),
        destination_connection_ids=[uuid.uuid4()],
        user_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        created_at=base_time - timedelta(hours=2),
        updated_at=base_time - timedelta(hours=1),
        organization_id=organization_id,
        status=SyncStatus.ACTIVE,
        cron_schedule="*/5 * * * *",  # Every 5 minutes
        next_scheduled_run=base_time - timedelta(minutes=2),  # In the past
        modified_at=base_time - timedelta(hours=1),
        created_by_email="test@example.com",
        modified_by_email="test@example.com",
    )

    # Sync that is not due yet (next_scheduled_run in the future)
    future_sync = schemas.Sync(
        id=uuid.uuid4(),
        name="Future Sync",
        description="Future sync description",
        source_connection_id=uuid.uuid4(),
        destination_connection_ids=[uuid.uuid4()],
        user_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        created_at=base_time - timedelta(hours=2),
        updated_at=base_time - timedelta(hours=1),
        organization_id=organization_id,
        status=SyncStatus.ACTIVE,
        cron_schedule="*/10 * * * *",  # Every 10 minutes
        next_scheduled_run=base_time + timedelta(minutes=5),  # In the future
        modified_at=base_time - timedelta(hours=1),
        created_by_email="test@example.com",
        modified_by_email="test@example.com",
    )

    # Sync with no next_scheduled_run (should be calculated)
    no_next_run_sync = schemas.Sync(
        id=uuid.uuid4(),
        name="No Next Run Sync",
        description="No next run sync description",
        source_connection_id=uuid.uuid4(),
        destination_connection_ids=[uuid.uuid4()],
        user_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        created_at=base_time - timedelta(hours=2),
        updated_at=base_time - timedelta(hours=1),
        organization_id=organization_id,
        status=SyncStatus.ACTIVE,
        cron_schedule="*/15 * * * *",  # Every 15 minutes
        next_scheduled_run=None,  # No next run time set
        modified_at=base_time - timedelta(hours=1),
        created_by_email="test@example.com",
        modified_by_email="test@example.com",
    )

    return [due_sync, future_sync, no_next_run_sync]


class TestEnsureUTC:
    """Tests for the ensure_utc function."""

    def test_ensure_utc_with_none(self):
        """Test ensure_utc with None input."""
        assert ensure_utc(None) is None

    def test_ensure_utc_with_naive_datetime(self):
        """Test ensure_utc with naive datetime."""
        naive_dt = datetime(2023, 1, 1, 12, 0, 0)
        utc_dt = ensure_utc(naive_dt)
        assert utc_dt.tzinfo is not None
        assert utc_dt.tzinfo.tzname(None) == "UTC"

    def test_ensure_utc_with_utc_datetime(self):
        """Test ensure_utc with UTC datetime."""
        utc_dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = ensure_utc(utc_dt)
        assert result == utc_dt
        assert result.tzinfo == timezone.utc


class TestPlatformSchedulerInit:
    """Tests for PlatformScheduler initialization."""

    def test_init(self):
        """Test initialization of PlatformScheduler."""
        scheduler = PlatformScheduler()
        assert scheduler.running is False
        assert scheduler.task is None
        assert scheduler.check_interval == 1


class TestUpdateAllNextScheduledRuns:
    """Tests for update_all_next_scheduled_runs method."""

    @pytest.mark.asyncio
    async def test_update_all_next_scheduled_runs_no_syncs(self):
        """Test update_all_next_scheduled_runs with no syncs."""
        scheduler = PlatformScheduler()

        # Mock the database session and query result
        mock_db_context = AsyncMock()
        mock_db = AsyncMock()
        mock_db_context.__aenter__.return_value = mock_db

        # Setup mock query result
        mock_scalar_result = Mock()
        mock_scalar_result.all.return_value = []
        mock_execute_result = Mock()
        mock_execute_result.scalars.return_value = mock_scalar_result

        # Make execute() an AsyncMock that returns the expected result
        # This allows it to be awaited while still returning a regular mock for results
        mock_db.execute = AsyncMock(return_value=mock_execute_result)

        with patch("airweave.platform.scheduler.get_db_context", return_value=mock_db_context):
            await scheduler.update_all_next_scheduled_runs()

        # Assert database was queried
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_all_next_scheduled_runs_with_syncs(
        self, mock_sync_with_schedule, mock_sync_job, mock_user
    ):
        """Test update_all_next_scheduled_runs with syncs."""
        scheduler = PlatformScheduler()

        # Mock database session
        mock_db_context = AsyncMock()
        mock_db = AsyncMock()
        mock_db_context.__aenter__.return_value = mock_db

        # Setup mock query result with syncs
        mock_scalar_result = Mock()
        mock_scalar_result.all.return_value = [mock_sync_with_schedule]
        mock_execute_result = Mock()
        mock_execute_result.scalars.return_value = mock_scalar_result

        # Make execute() an AsyncMock that returns the expected result
        mock_db.execute = AsyncMock(return_value=mock_execute_result)

        # Use the actual mock_user directly
        with (
            patch("airweave.platform.scheduler.get_db_context", return_value=mock_db_context),
            patch(
                "airweave.platform.scheduler.crud.sync_job.get_latest_by_sync_id",
                new_callable=AsyncMock,
                return_value=mock_sync_job,
            ),
            patch(
                "airweave.platform.scheduler.crud.user.get_by_email",
                new_callable=AsyncMock,
                return_value=mock_user,
            ),
            patch(
                "airweave.platform.scheduler.crud.sync.get",
                new_callable=AsyncMock,
                return_value=mock_sync_with_schedule,
            ),
            patch("airweave.platform.scheduler.crud.sync.update", new_callable=AsyncMock),
        ):
            await scheduler.update_all_next_scheduled_runs()

            # Assert crud operations were called
            crud.sync_job.get_latest_by_sync_id.assert_called_once_with(
                mock_db, sync_id=mock_sync_with_schedule.id
            )
            crud.user.get_by_email.assert_called_once_with(
                mock_db, email=mock_sync_with_schedule.created_by_email
            )
            crud.sync.get.assert_called_once()
            crud.sync.update.assert_called_once()


class TestSchedulerStartStop:
    """Tests for scheduler start and stop methods."""

    @pytest.mark.asyncio
    async def test_start(self):
        """Test starting the scheduler."""
        scheduler = PlatformScheduler()

        # Mock methods
        scheduler.update_all_next_scheduled_runs = AsyncMock()

        # Create a dummy task
        dummy_task = asyncio.create_task(asyncio.sleep(0))

        with patch("asyncio.create_task", return_value=dummy_task):
            await scheduler.start()

            # Assert methods called and flags set
            scheduler.update_all_next_scheduled_runs.assert_called_once()
            assert scheduler.running is True
            asyncio.create_task.assert_called_once()

        # Cleanup
        if not dummy_task.done():
            dummy_task.cancel()
            try:
                await dummy_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_start_already_running(self):
        """Test starting the scheduler when it's already running."""
        scheduler = PlatformScheduler()
        scheduler.running = True

        # Mock methods
        scheduler.update_all_next_scheduled_runs = AsyncMock()

        await scheduler.start()

        # Assert update method not called again
        scheduler.update_all_next_scheduled_runs.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop(self):
        """Test stopping the scheduler."""
        scheduler = PlatformScheduler()
        scheduler.running = True

        # Create a real task for the test
        dummy_task = asyncio.create_task(asyncio.sleep(1))
        scheduler.task = dummy_task

        await scheduler.stop()

        # Assert task cancelled and flags reset
        assert scheduler.running is False
        assert dummy_task.cancelled()

    @pytest.mark.asyncio
    async def test_stop_not_running(self):
        """Test stopping the scheduler when it's not running."""
        scheduler = PlatformScheduler()
        scheduler.running = False
        scheduler.task = None

        await scheduler.stop()

        # Nothing should happen
        assert scheduler.running is False
        assert scheduler.task is None


class TestSchedulerLoop:
    """Tests for the scheduler loop functionality."""

    @pytest.mark.asyncio
    async def test_scheduler_loop(self):
        """Test the scheduler loop functionality."""
        scheduler = PlatformScheduler()

        # Set up to run only once
        scheduler.running = True

        # Mock sleep to stop after one iteration
        async def mock_sleep(*args, **kwargs):
            scheduler.running = False

        # Mock methods
        scheduler._check_syncs = AsyncMock()

        with patch("asyncio.sleep", mock_sleep):
            await scheduler._scheduler_loop()

            # Assert check_syncs called
            scheduler._check_syncs.assert_called_once()
            assert scheduler.running is False


class TestGetActiveSync:
    """Tests for _get_active_syncs_with_schedule method."""

    @pytest.mark.asyncio
    async def test_get_active_syncs_with_schedule(self, mock_sync_multiple):
        """Test getting active syncs with schedules."""
        scheduler = PlatformScheduler()
        mock_db = AsyncMock()

        # Setup mock query results for db.execute
        mock_scalar_result = Mock()
        mock_scalar_result.unique = Mock(return_value=mock_scalar_result)  # Add unique() mock
        mock_scalar_result.all.return_value = mock_sync_multiple
        mock_execute_result = Mock()
        mock_execute_result.scalars.return_value = mock_scalar_result

        # Make execute() an AsyncMock that returns the expected result
        mock_db.execute = AsyncMock(return_value=mock_execute_result)

        # Mock crud.sync.get_all_with_schedule to return the mock_sync_multiple directly
        with patch(
            "airweave.platform.scheduler.crud.sync.get_all_with_schedule",
            new_callable=AsyncMock,
            return_value=mock_sync_multiple,
        ):
            result = await scheduler._get_active_syncs_with_schedule(mock_db)

            # Assert database was queried and results processed
            crud.sync.get_all_with_schedule.assert_called_once_with(mock_db)
            assert len(result) == len(mock_sync_multiple)


class TestProcessSync:
    """Tests for _process_sync method."""

    @pytest.mark.asyncio
    async def test_process_sync_due(self, mock_sync_multiple):
        """Test processing a sync that is due."""
        due_sync = mock_sync_multiple[0]  # Get the due sync
        scheduler = PlatformScheduler()
        mock_db = AsyncMock()

        # Create a proper mock user that will pass Pydantic validation
        mock_user = schemas.User(
            id=uuid.uuid4(),
            email="test@example.com",
            full_name="Test User",
            organization_id=uuid.uuid4(),
            is_active=True,
        )

        # Set up a datetime that will make the sync due
        now = datetime.now(timezone.utc)
        next_run = now - timedelta(minutes=5)  # 5 minutes in the past

        # Mock database operations
        with (
            patch(
                "airweave.platform.scheduler.crud.user.get_by_email",
                new_callable=AsyncMock,
                return_value=mock_user,
            ),
            patch(
                "airweave.platform.scheduler.crud.sync_job.get_latest_by_sync_id",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "airweave.platform.scheduler.crud.sync.get",
                new_callable=AsyncMock,
                return_value=due_sync,
            ),
            patch("airweave.platform.scheduler.crud.sync.update", new_callable=AsyncMock),
            patch(
                "airweave.platform.scheduler.PlatformScheduler._trigger_sync",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("airweave.platform.scheduler.datetime") as mock_datetime,
            patch("airweave.platform.scheduler.croniter") as mock_croniter,
        ):
            # Set the mock datetime to return our fixed "now"
            mock_datetime.now.return_value = now
            mock_datetime.fromtimestamp.return_value = datetime.fromtimestamp(0, tz=timezone.utc)

            # Make croniter return our fixed next_run time
            mock_cron = MagicMock()
            mock_cron.get_next.return_value = next_run
            mock_croniter.return_value = mock_cron

            result = await scheduler._process_sync(mock_db, due_sync)

            # Assert sync was triggered
            assert result is True
            scheduler._trigger_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_sync_not_due(self, mock_sync_multiple):
        """Test processing a sync that is not due yet."""
        not_due_sync = mock_sync_multiple[1]  # Get the future sync
        scheduler = PlatformScheduler()
        mock_db = AsyncMock()

        # Create a proper mock user that will pass Pydantic validation
        mock_user = schemas.User(
            id=uuid.uuid4(),
            email="test@example.com",
            full_name="Test User",
            organization_id=uuid.uuid4(),
            is_active=True,
        )

        # Set up a datetime that will make the sync not due
        now = datetime.now(timezone.utc)
        next_run = now + timedelta(minutes=5)  # 5 minutes in the future

        # Mock crud operations and time functions
        with (
            patch(
                "airweave.platform.scheduler.crud.user.get_by_email",
                new_callable=AsyncMock,
                return_value=mock_user,
            ),
            patch(
                "airweave.platform.scheduler.crud.sync_job.get_latest_by_sync_id",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "airweave.platform.scheduler.crud.sync.get",
                new_callable=AsyncMock,
                return_value=not_due_sync,
            ),
            patch("airweave.platform.scheduler.crud.sync.update", new_callable=AsyncMock),
            patch("airweave.platform.scheduler.datetime") as mock_datetime,
            patch("airweave.platform.scheduler.croniter") as mock_croniter,
        ):
            # Set the mock datetime to return our fixed "now"
            mock_datetime.now.return_value = now
            mock_datetime.fromtimestamp.return_value = datetime.fromtimestamp(0, tz=timezone.utc)

            # Make croniter return our fixed next_run time
            mock_cron = MagicMock()
            mock_cron.get_next.return_value = next_run
            mock_croniter.return_value = mock_cron

            result = await scheduler._process_sync(mock_db, not_due_sync)

            # Assert sync was not triggered (not due yet)
            assert result is False

    @pytest.mark.asyncio
    async def test_process_sync_job_in_progress(self, mock_sync_with_schedule, mock_sync_job):
        """Test processing a sync that already has a job in progress."""
        scheduler = PlatformScheduler()
        mock_db = AsyncMock()

        # Set the job status to IN_PROGRESS
        in_progress_job = mock_sync_job
        in_progress_job.status = SyncJobStatus.IN_PROGRESS

        # Create a proper mock user that will pass Pydantic validation
        mock_user = schemas.User(
            id=uuid.uuid4(),
            email="test@example.com",
            full_name="Test User",
            organization_id=uuid.uuid4(),
            is_active=True,
        )

        # Mock necessary crud operations
        with (
            patch(
                "airweave.platform.scheduler.crud.user.get_by_email",
                new_callable=AsyncMock,
                return_value=mock_user,
            ),
            patch(
                "airweave.platform.scheduler.crud.sync_job.get_latest_by_sync_id",
                new_callable=AsyncMock,
                return_value=in_progress_job,
            ),
        ):
            result = await scheduler._process_sync(mock_db, mock_sync_with_schedule)

            # Assert sync was not triggered (job in progress)
            assert result is False


class TestTriggerSync:
    """Tests for _trigger_sync method."""

    @pytest.mark.asyncio
    async def test_trigger_sync(
        self, mock_sync_with_schedule, mock_sync_job, mock_sync_dag, mock_user
    ):
        """Test triggering a sync job."""
        scheduler = PlatformScheduler()
        mock_db = AsyncMock()

        # Create mock source connection with proper field values for Pydantic validation
        mock_source_connection = MagicMock()
        mock_source_connection.id = uuid.uuid4()
        mock_source_connection.name = "Test Source Connection"
        mock_source_connection.short_name = "test_source"
        mock_source_connection.readable_collection_id = "test-collection"
        mock_source_connection.organization_id = uuid.uuid4()
        mock_source_connection.created_at = datetime.now(timezone.utc)
        mock_source_connection.modified_at = datetime.now(timezone.utc)
        mock_source_connection.created_by_email = "test@example.com"
        mock_source_connection.modified_by_email = "test@example.com"

        # Create mock collection with proper field values for Pydantic validation
        mock_collection = MagicMock()
        mock_collection.id = uuid.uuid4()
        mock_collection.readable_id = "test-collection"
        mock_collection.name = "Test Collection"
        mock_collection.organization_id = uuid.uuid4()
        mock_collection.created_by_email = "test@example.com"
        mock_collection.modified_by_email = "test@example.com"
        mock_collection.status = "ACTIVE"

        # Mock crud operations
        with (
            patch("airweave.platform.scheduler.get_db_context") as mock_get_db,
            patch(
                "airweave.platform.scheduler.crud.user.get_by_email",
                new_callable=AsyncMock,
                return_value=mock_user,
            ),
            patch(
                "airweave.platform.scheduler.crud.sync_job.create",
                new_callable=AsyncMock,
                return_value=mock_sync_job,
            ),
            patch(
                "airweave.platform.scheduler.crud.sync_dag.get_by_sync_id",
                new_callable=AsyncMock,
                return_value=mock_sync_dag,
            ),
            patch(
                "airweave.platform.scheduler.crud.source_connection.get_by_sync_id",
                new_callable=AsyncMock,
                return_value=mock_source_connection,
            ),
            patch(
                "airweave.platform.scheduler.crud.collection.get_by_readable_id",
                new_callable=AsyncMock,
                return_value=mock_collection,
            ),
            patch(
                "airweave.platform.scheduler.temporal_service.is_temporal_enabled",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("asyncio.create_task"),
            patch("airweave.platform.scheduler.sync_service.run"),
        ):
            # Configure mock_get_db
            db_context = AsyncMock()
            db_context.__aenter__.return_value = mock_db
            mock_get_db.return_value = db_context

            # Execute method
            await scheduler._trigger_sync(mock_db, mock_sync_with_schedule)

            # Assert crud operations were called
            crud.user.get_by_email.assert_called_once()
            crud.sync_job.create.assert_called_once()
            crud.sync_dag.get_by_sync_id.assert_called_once()
            asyncio.create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_sync_user_not_found(self, mock_sync_with_schedule):
        """Test triggering a sync with a user that doesn't exist."""
        scheduler = PlatformScheduler()
        mock_db = AsyncMock()

        # Mock user not found
        with patch(
            "airweave.platform.scheduler.crud.user.get_by_email",
            new_callable=AsyncMock,
            return_value=None,
        ):
            # Execute method
            await scheduler._trigger_sync(mock_db, mock_sync_with_schedule)

            # Assert user lookup was attempted
            crud.user.get_by_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_sync_no_dag(self, mock_sync_with_schedule, mock_user):
        """Test triggering a sync with no DAG."""
        scheduler = PlatformScheduler()
        mock_db = AsyncMock()

        # Mock crud operations
        with (
            patch("airweave.platform.scheduler.get_db_context"),
            patch(
                "airweave.platform.scheduler.crud.user.get_by_email",
                new_callable=AsyncMock,
                return_value=mock_user,
            ),
            patch("airweave.platform.scheduler.crud.sync_job.create", new_callable=AsyncMock),
            patch(
                "airweave.platform.scheduler.crud.sync_dag.get_by_sync_id",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            # Execute method
            await scheduler._trigger_sync(mock_db, mock_sync_with_schedule)

            # Assert crud operations were called
            crud.user.get_by_email.assert_called_once()
            crud.sync_job.create.assert_called_once()
            crud.sync_dag.get_by_sync_id.assert_called_once()
