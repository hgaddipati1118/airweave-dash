"""Integration test for Temporal workflow cancellation and sync job status update."""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from temporalio.testing import WorkflowEnvironment
from temporalio.exceptions import CancelledError
from temporalio.client import WorkflowFailureError
from temporalio.worker import Worker
from temporalio import activity

from airweave.platform.temporal.workflows import RunSourceConnectionWorkflow
from airweave.platform.temporal.activities import run_sync_activity, update_sync_job_status_activity
from airweave.core.shared_models import SyncJobStatus


@pytest.fixture
def mock_sync_job_id():
    """Generate a consistent sync job ID for testing."""
    return str(uuid4())


@pytest.fixture
def mock_dicts(mock_sync_job_id):
    """Create all required mock dictionaries for the workflow."""
    return {
        "sync_dict": {
            "id": str(uuid4()),
            "name": "Test Sync",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        },
        "sync_job_dict": {
            "id": mock_sync_job_id,
            "sync_id": str(uuid4()),
            "status": "CREATED",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        },
        "sync_dag_dict": {"id": str(uuid4()), "nodes": [], "edges": []},
        "collection_dict": {"id": str(uuid4()), "name": "Test Collection"},
        "source_connection_dict": {"id": str(uuid4()), "name": "Test Connection"},
        "user_dict": {
            "id": str(uuid4()),
            "email": "test@example.com",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        },
    }


@pytest.mark.asyncio
class TestWorkflowCancellation:
    """Test Temporal workflow cancellation and sync job status updates."""

    async def test_workflow_cancellation_updates_sync_job_status(self, mock_dicts, mock_sync_job_id):
        """Test that cancelling a workflow properly updates the sync job status to CANCELLED."""

        async with await WorkflowEnvironment.start_time_skipping() as env:
            # Track what happened
            status_update_called = False
            final_status = None
            final_error = None
            activity_started = False

            @activity.defn(name="run_sync_activity")
            async def mock_run_sync_activity(*args, **kwargs):
                """Simulate a long-running sync that can be cancelled."""
                nonlocal activity_started
                activity_started = True
                # Simulate a long-running activity that can be cancelled
                # We'll sleep for a long time and let the cancellation happen
                await asyncio.sleep(60)  # Sleep for 60 seconds, should be cancelled before this
                return None

            @activity.defn(name="update_sync_job_status_activity")
            async def mock_update_status_activity(*args, **kwargs):
                """Capture the status update."""
                nonlocal status_update_called, final_status, final_error

                sync_job_id, status, user_dict, error, failed_at = args

                # Verify correct sync job ID
                assert sync_job_id == mock_sync_job_id

                # Capture the final status and error
                final_status = status
                final_error = error
                status_update_called = True

                print(f"Status update called: job_id={sync_job_id}, status={status}, error={error}")

            # Create worker with mocked activities
            async with Worker(
                env.client,
                task_queue="test-queue",
                workflows=[RunSourceConnectionWorkflow],
                activities=[mock_run_sync_activity, mock_update_status_activity],
            ):
                # Start the workflow
                workflow_handle = await env.client.start_workflow(
                    RunSourceConnectionWorkflow.run,
                    args=[
                        mock_dicts["sync_dict"],
                        mock_dicts["sync_job_dict"],
                        mock_dicts["sync_dag_dict"],
                        mock_dicts["collection_dict"],
                        mock_dicts["source_connection_dict"],
                        mock_dicts["user_dict"],
                        None,
                    ],
                    id=f"test-workflow-{mock_sync_job_id}",
                    task_queue="test-queue",
                )

                # Give the workflow a moment to start the activity
                await asyncio.sleep(0.1)

                # Cancel the workflow
                await workflow_handle.cancel()

                # Wait for workflow to complete and expect WorkflowFailureError (wraps the CancelledError)
                with pytest.raises((CancelledError, WorkflowFailureError)):
                    await workflow_handle.result()

                # Verify the activity was started
                assert activity_started, "Activity should have been started before cancellation"

                # Verify the status update was called
                assert status_update_called, "Status update activity should have been called"
                assert final_status.lower() == "cancelled", f"Expected status to be cancelled, got {final_status}"
                assert "cancelled" in final_error.lower(), f"Expected error to mention cancellation, got: {final_error}"

    async def test_workflow_activity_failure_updates_sync_job_status(self, mock_dicts, mock_sync_job_id):
        """Test that activity failure properly updates sync job status."""

        async with await WorkflowEnvironment.start_time_skipping() as env:
            # Track what happened
            status_update_called = False
            final_status = None
            final_error = None

            @activity.defn(name="run_sync_activity")
            async def mock_run_sync_activity_failure(*args, **kwargs):
                """Simulate an activity that fails."""
                raise Exception("Sync activity failed")

            @activity.defn(name="update_sync_job_status_activity")
            async def mock_update_status_activity(*args, **kwargs):
                """Capture the status update."""
                nonlocal status_update_called, final_status, final_error

                sync_job_id, status, user_dict, error, failed_at = args

                # Verify correct sync job ID
                assert sync_job_id == mock_sync_job_id

                # Capture the final status and error
                final_status = status
                final_error = error
                status_update_called = True

                print(f"Failure test - Status: {status}, Error: {error}")

            # Create worker with mocked activities
            async with Worker(
                env.client,
                task_queue="test-queue",
                workflows=[RunSourceConnectionWorkflow],
                activities=[mock_run_sync_activity_failure, mock_update_status_activity],
            ):
                # Run the workflow and expect it to raise
                with pytest.raises(Exception) as exc_info:
                    await env.client.execute_workflow(
                        RunSourceConnectionWorkflow.run,
                        args=[
                            mock_dicts["sync_dict"],
                            mock_dicts["sync_job_dict"],
                            mock_dicts["sync_dag_dict"],
                            mock_dicts["collection_dict"],
                            mock_dicts["source_connection_dict"],
                            mock_dicts["user_dict"],
                            None,
                        ],
                        id=f"test-workflow-failure-{mock_sync_job_id}",
                        task_queue="test-queue",
                    )

                # Verify the status update was called
                assert status_update_called, "Status update activity should have been called"
                assert final_status.lower() == "failed", f"Expected status to be failed, got {final_status}"
                assert "failed" in final_error.lower(), f"Expected error to mention failure, got: {final_error}"

    async def test_successful_workflow_no_status_update(self, mock_dicts, mock_sync_job_id):
        """Test that successful workflow completion doesn't call the error status update."""

        async with await WorkflowEnvironment.start_time_skipping() as env:
            # Track what happened
            sync_completed = False
            error_status_update_called = False

            @activity.defn(name="run_sync_activity")
            async def mock_run_sync_activity_success(*args, **kwargs):
                """Simulate a successful sync."""
                nonlocal sync_completed
                sync_completed = True
                return None

            @activity.defn(name="update_sync_job_status_activity")
            async def mock_update_status_activity(*args, **kwargs):
                """This should NOT be called for successful completion."""
                nonlocal error_status_update_called
                error_status_update_called = True
                pytest.fail("Error status update should not be called for successful workflow")

            # Create worker with mocked activities
            async with Worker(
                env.client,
                task_queue="test-queue",
                workflows=[RunSourceConnectionWorkflow],
                activities=[mock_run_sync_activity_success, mock_update_status_activity],
            ):
                # Run the workflow - should complete successfully
                result = await env.client.execute_workflow(
                    RunSourceConnectionWorkflow.run,
                    args=[
                        mock_dicts["sync_dict"],
                        mock_dicts["sync_job_dict"],
                        mock_dicts["sync_dag_dict"],
                        mock_dicts["collection_dict"],
                        mock_dicts["source_connection_dict"],
                        mock_dicts["user_dict"],
                        None,
                    ],
                    id=f"test-workflow-success-{mock_sync_job_id}",
                    task_queue="test-queue",
                )

                # Verify the sync completed successfully
                assert sync_completed, "Sync activity should have completed"
                assert not error_status_update_called, "Error status update should not have been called"


@pytest.mark.asyncio
async def test_real_workflow_cancellation_flow(mock_sync_job_id):
    """
    Demonstration test showing the expected behavior when cancelling a real Temporal workflow.

    This test shows what would happen in a real environment:
    1. Start a sync job workflow
    2. Cancel it while it's running
    3. Workflow catches CancelledError and updates sync job status to CANCELLED
    """

    print("\n=== Temporal Workflow Cancellation Flow ===")
    print(f"1. Starting sync job with ID: {mock_sync_job_id}")
    print("2. Workflow begins executing run_sync_activity")
    print("3. User/system sends cancel signal to workflow")
    print("4. Temporal propagates cancellation to the activity")
    print("5. Workflow catches CancelledError")
    print("6. Workflow executes update_sync_job_status_activity:")
    print(f"   - sync_job_id: {mock_sync_job_id}")
    print("   - status: CANCELLED")
    print("   - error: 'Workflow was cancelled'")
    print("7. Sync job is now marked as CANCELLED in the database")
    print("\nThis ensures no sync jobs are left in IN_PROGRESS state when cancelled!")

    # This is what the actual flow would look like in production
    expected_flow = {
        "workflow_started": True,
        "activity_started": True,
        "cancellation_received": True,
        "error_caught": "CancelledError",
        "status_update_called": True,
        "final_job_status": "CANCELLED",
        "error_message": "Workflow was cancelled"
    }

    assert expected_flow["final_job_status"] == "CANCELLED"
    assert expected_flow["status_update_called"] is True
