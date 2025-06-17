"""E2E test runner for Airweave.

This module provides utilities to run end-to-end tests with docker-compose.
"""

import logging

from ..helpers.docker import DockerComposeManager

logger = logging.getLogger(__name__)


class E2ETestRunner:
    """Runner for E2E tests that manages docker-compose services.

    This is a thin wrapper around DockerComposeManager that provides
    a consistent interface for E2E tests. All Docker-specific functionality
    is delegated to the DockerComposeManager.
    """

    def __init__(self, compose_file: str = "../../docker/docker-compose.test.yml"):
        """Initialize the E2E test runner.

        Args:
            compose_file: Path to the docker-compose file for testing, relative to tests directory
        """
        # Initialize the Docker Compose manager
        self.docker = DockerComposeManager(compose_file=compose_file)

        logger.info(f"Initialized E2E test runner with compose file: {compose_file}")

    def setup(self, force_rebuild: bool = False) -> None:
        """Start all services for E2E tests.

        Args:
            force_rebuild: If True, force rebuild the backend container
        """
        logger.info("Starting services for E2E tests")
        try:
            # Set environment variable for force rebuild if needed
            if force_rebuild:
                logger.info("Force rebuild enabled for backend container")
                self.docker.start(force_rebuild=True)
            else:
                self.docker.start()
            logger.info("All services are running and ready")

        except Exception as e:
            logger.error(f"Error during service startup: {e}")
            self.teardown()  # Clean up any started services
            raise

    def teardown(self) -> None:
        """Stop all services after tests."""
        logger.info("Stopping services")
        try:
            # Don't remove volumes by default to enable reuse
            self.docker.stop(remove_volumes=False)
        except Exception as e:
            logger.error(f"Error during service teardown: {e}")
            raise
