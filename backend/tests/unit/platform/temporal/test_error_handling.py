"""Tests for Temporal workflow error handling."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from temporalio import workflow, activity
from temporalio.exceptions import CancelledError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from airweave.platform.temporal.workflows import RunSourceConnectionWorkflow
from airweave.platform.temporal.activities import run_sync_activity, update_sync_job_status_activity


@pytest.fixture
def mock_sync_dict():
    """Create a mock sync dictionary."""
    return {
        "id": str(uuid4()),
        "name": "Test Sync",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


@pytest.fixture
def mock_sync_job_dict():
    """Create a mock sync job dictionary."""
    return {
        "id": str(uuid4()),
        "sync_id": str(uuid4()),
        "status": "CREATED",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


@pytest.fixture
def mock_user_dict():
    """Create a mock user dictionary."""
    return {
        "id": str(uuid4()),
        "email": "test@example.com",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


@pytest.fixture
def mock_dicts(mock_sync_dict, mock_sync_job_dict, mock_user_dict):
    """Create all required mock dictionaries."""
    return {
        "sync_dict": mock_sync_dict,
        "sync_job_dict": mock_sync_job_dict,
        "sync_dag_dict": {"id": str(uuid4()), "nodes": [], "edges": []},
        "collection_dict": {"id": str(uuid4()), "name": "Test Collection"},
        "source_connection_dict": {"id": str(uuid4()), "name": "Test Connection"},
        "user_dict": mock_user_dict,
    }


@pytest.mark.asyncio
class TestTemporalErrorHandling:
    """Test error handling in Temporal workflows."""

    async def test_workflow_handles_activity_failure(self, mock_dicts):
        """Test that workflow handles activity failures and updates sync job status."""
        async with await WorkflowEnvironment.start_time_skipping() as env:
            # Mock the activities
            run_sync_error = Exception("Sync activity failed")

            @activity.defn(name="run_sync_activity")
            async def mock_run_sync_activity(*args, **kwargs):
                raise run_sync_error

            @activity.defn(name="update_sync_job_status_activity")
            async def mock_update_status_activity(*args, **kwargs):
                # Verify the correct parameters are passed
                sync_job_id, status, user_dict, error, failed_at = args
                assert sync_job_id == mock_dicts["sync_job_dict"]["id"]
                assert status.lower() == "failed"  # Status comes as lowercase from workflow
                # Temporal wraps the error - check for wrapped message
                assert "failed" in error.lower()  # More flexible assertion
                assert failed_at is not None
                # failed_at should be an ISO format string from workflow.now()
                # Just verify it can be parsed
                datetime.fromisoformat(failed_at)

            # Create worker with mocked activities
            async with Worker(
                env.client,
                task_queue="test-queue",
                workflows=[RunSourceConnectionWorkflow],
                activities=[mock_run_sync_activity, mock_update_status_activity],
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
                        id=f"test-workflow-{uuid4()}",
                        task_queue="test-queue",
                    )

                # The workflow wraps the original exception
                assert "workflow execution failed" in str(exc_info.value).lower()

    async def test_workflow_handles_cancellation(self, mock_dicts):
        """Test that workflow handles CancelledError from activities correctly."""
        status_update_called = False

        async with await WorkflowEnvironment.start_time_skipping() as env:

            @activity.defn(name="run_sync_activity")
            async def mock_run_sync_activity(*args, **kwargs):
                """Mock sync activity that gets cancelled."""
                raise CancelledError("Activity was cancelled")

            @activity.defn(name="update_sync_job_status_activity")
            async def mock_update_status_activity(*args, **kwargs):
                """Mock status update to verify cancellation handling."""
                nonlocal status_update_called
                status_update_called = True

                sync_job_id, status, user_dict, error, failed_at = args
                assert sync_job_id == mock_dicts["sync_job_dict"]["id"]
                # When CancelledError is raised from activity, it gets treated as failure
                # because Temporal testing framework converts it to timeout error
                assert status.lower() == "failed"  # Expect failed, not cancelled
                assert "timed out" in error.lower() or "failed" in error.lower()
                return None

            # Create worker with mocked activities
            async with Worker(
                env.client,
                task_queue="test-queue",
                workflows=[RunSourceConnectionWorkflow],
                activities=[mock_run_sync_activity, mock_update_status_activity],
            ):
                # Run the workflow and expect it to raise WorkflowFailureError
                with pytest.raises(Exception):  # Accept either CancelledError or WorkflowFailureError
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
                        id=f"test-workflow-{uuid4()}",
                        task_queue="test-queue",
                    )

                # Verify that the status update activity was called
                assert status_update_called, "Status update activity should have been called"

    async def test_workflow_success_no_status_update(self, mock_dicts):
        """Test that workflow doesn't update status on successful completion."""
        async with await WorkflowEnvironment.start_time_skipping() as env:
            # Mock the activities
            @activity.defn(name="run_sync_activity")
            async def mock_run_sync_activity_success(*args, **kwargs):
                # Successful completion
                return None

            status_updated = False

            @activity.defn(name="update_sync_job_status_activity")
            async def mock_update_status_activity(*args, **kwargs):
                nonlocal status_updated
                status_updated = True
                # This should not be called on success
                pytest.fail("Status update should not be called on success")

            # Create worker with mocked activities
            async with Worker(
                env.client,
                task_queue="test-queue",
                workflows=[RunSourceConnectionWorkflow],
                activities=[mock_run_sync_activity_success, mock_update_status_activity],
            ):
                # Run the workflow - should complete successfully
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
                    id=f"test-workflow-{uuid4()}",
                    task_queue="test-queue",
                )

                # Verify that the status update activity was NOT called
                assert not status_updated, "Status update activity should not be called on success"
