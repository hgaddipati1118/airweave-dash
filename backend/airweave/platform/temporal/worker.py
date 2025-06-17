"""Temporal worker for Airweave."""

import asyncio
import os
import signal
from typing import Any

from temporalio.worker import Worker

from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.platform.entities._base import ensure_file_entity_models
from airweave.platform.temporal.activities import run_sync_activity, update_sync_job_status_activity
from airweave.platform.temporal.client import temporal_client
from airweave.platform.temporal.workflows import RunSourceConnectionWorkflow


class TemporalWorker:
    """Temporal worker for processing workflows and activities."""

    def __init__(self) -> None:
        """Initialize the Temporal worker."""
        self.worker: Worker | None = None
        self.running = False

    async def start(self) -> None:
        """Start the Temporal worker."""
        try:
            # Ensure all FileEntity subclasses have their parent and chunk models created
            ensure_file_entity_models()

            client = await temporal_client.get_client()

            task_queue = settings.TEMPORAL_TASK_QUEUE

            logger.info(f"Starting Temporal worker on task queue: {task_queue}")

            # Configure sandbox to allow debugger modules if debugging
            disable_sandbox = os.environ.get("TEMPORAL_DISABLE_SANDBOX", "").lower() == "true"

            if disable_sandbox:
                # Completely disable sandboxing (debugging only!)
                from temporalio.worker import UnsandboxedWorkflowRunner

                sandbox_config = UnsandboxedWorkflowRunner()
                logger.warning("⚠️  TEMPORAL SANDBOX DISABLED - Use only for debugging!")
            elif (
                settings.DEBUG
                or getattr(settings, "ALLOW_DEBUGGER", False)
                or os.environ.get("DEBUG", "").lower() == "true"
            ):
                # Allow debugger modules to pass through the sandbox
                from temporalio.worker.workflow_sandbox import (
                    SandboxedWorkflowRunner,
                    SandboxRestrictions,
                )

                restrictions = SandboxRestrictions.default.with_passthrough_modules(
                    "_pydevd_bundle",
                    "pydevd",
                    "debugpy",
                )
                sandbox_config = SandboxedWorkflowRunner(restrictions=restrictions)
                logger.warning(
                    "Running with debugger support - workflow sandbox restrictions relaxed"
                )
            else:
                # Default sandbox configuration for production
                from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner

                sandbox_config = SandboxedWorkflowRunner()
                logger.info("Using default sandboxed workflow runner")

            self.worker = Worker(
                client,
                task_queue=task_queue,
                workflows=[RunSourceConnectionWorkflow],
                activities=[run_sync_activity, update_sync_job_status_activity],
                workflow_runner=sandbox_config,
            )

            self.running = True
            await self.worker.run()

        except Exception as e:
            logger.error(f"Error starting Temporal worker: {e}")
            raise

    async def stop(self) -> None:
        """Stop the Temporal worker."""
        if self.worker and self.running:
            logger.info("Stopping Temporal worker...")
            self.running = False
            await self.worker.shutdown()

        # Always close temporal client to prevent resource leaks
        await temporal_client.close()


async def main() -> None:
    """Main function to run the worker."""
    worker = TemporalWorker()

    # Handle shutdown signals
    def signal_handler(signum: int, frame: Any) -> None:
        logger.info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(worker.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
