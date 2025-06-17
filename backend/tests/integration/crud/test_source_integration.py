"""Integration tests for the Source CRUD operations.

These tests use a real database connection to verify that the CRUD operations
work correctly with SQLAlchemy and the database.
"""

import logging
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.crud.crud_source import source as crud_source
from airweave.schemas.source import SourceCreate, SourceUpdate

logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_and_get_source(db_session: AsyncSession, skip_if_no_db):
    """Test creating and then retrieving a source."""
    # Create a unique short_name with a uuid to avoid conflicts
    unique_id = uuid.uuid4().hex[:8]

    # Arrange
    source_data = SourceCreate(
        name="Test Integration Source",
        short_name=f"test_source_{unique_id}",
        class_name="TestSourceConnector",
        auth_type=None,
        auth_config_class="TestAuthConfig",
        config_class="TestConfig",
        description="A test source for integration testing",
        organization_id=None,
        output_entity_definition_ids=[],
        config_schema={"type": "object", "properties": {}},
    )

    try:
        # Act - Create
        created_source = await crud_source.create(db=db_session, obj_in=source_data)

        # Assert - Create
        assert created_source is not None
        assert created_source.name == source_data.name
        assert created_source.short_name == source_data.short_name
        assert created_source.class_name == source_data.class_name
        assert created_source.id is not None

        # Act - Get by ID
        retrieved_source = await crud_source.get(db=db_session, id=created_source.id)

        # Assert - Get by ID
        assert retrieved_source is not None
        assert retrieved_source.id == created_source.id
        assert retrieved_source.name == source_data.name
        assert retrieved_source.short_name == source_data.short_name

        # Act - Get by short_name
        retrieved_by_short_name = await crud_source.get_by_short_name(
            db=db_session, short_name=source_data.short_name
        )

        # Assert - Get by short_name
        assert retrieved_by_short_name is not None
        assert retrieved_by_short_name.id == created_source.id
        assert retrieved_by_short_name.name == source_data.name

    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_source(db_session: AsyncSession, skip_if_no_db):
    """Test updating a source."""
    # Create a unique short_name with a uuid to avoid conflicts
    unique_id = uuid.uuid4().hex[:8]

    # Arrange - Create a source to update
    source_data = SourceCreate(
        name="Source To Update",
        short_name=f"update_source_{unique_id}",
        class_name="TestSourceConnector",
        auth_type=None,
        auth_config_class="TestAuthConfig",
        config_class="TestConfig",
        description="A source that will be updated",
        organization_id=None,
        output_entity_definition_ids=[],
        config_schema={"type": "object", "properties": {}},
    )

    try:
        created_source = await crud_source.create(db=db_session, obj_in=source_data)

        # Create update data
        update_data = SourceUpdate(
            name="Updated Source Name",
            short_name=created_source.short_name,
            class_name=created_source.class_name,
            auth_type=None,
            auth_config_class="UpdatedTestAuthConfig",
            config_class="UpdatedTestConfig",
            description="This source has been updated",
            organization_id=None,
            output_entity_definition_ids=[],
            config_schema={"type": "object", "properties": {}},
        )

        # Act
        updated_source = await crud_source.update(
            db=db_session, db_obj=created_source, obj_in=update_data
        )

        # Assert
        assert updated_source is not None
        assert updated_source.id == created_source.id
        assert updated_source.name == update_data.name
        assert updated_source.description == update_data.description
        assert updated_source.short_name == created_source.short_name

        # Verify the update in the database
        retrieved_source = await crud_source.get(db=db_session, id=created_source.id)
        assert retrieved_source is not None
        assert retrieved_source.name == update_data.name
        assert retrieved_source.description == update_data.description

    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_source(db_session: AsyncSession, skip_if_no_db):
    """Test deleting a source."""
    # Create a unique short_name with a uuid to avoid conflicts
    unique_id = uuid.uuid4().hex[:8]

    # Arrange - Create a source to delete
    source_data = SourceCreate(
        name="Source To Delete",
        short_name=f"delete_source_{unique_id}",
        class_name="TestSourceConnector",
        auth_type=None,
        auth_config_class="TestAuthConfig",
        config_class="TestConfig",
        description="A source that will be deleted",
        organization_id=None,
        output_entity_definition_ids=[],
        config_schema={"type": "object", "properties": {}},
    )

    try:
        created_source = await crud_source.create(db=db_session, obj_in=source_data)
        source_id = created_source.id

        # Verify it exists
        assert await crud_source.get(db=db_session, id=source_id) is not None

        # Act
        deleted_source = await crud_source.remove(db=db_session, id=source_id)

        # Assert
        assert deleted_source is not None
        assert deleted_source.id == source_id

        # Verify it's deleted
        assert await crud_source.get(db=db_session, id=source_id) is None

    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_all_sources(db_session: AsyncSession, skip_if_no_db):
    """Test getting all sources with pagination."""
    # Arrange - Create multiple sources
    sources_to_create = 5
    created_ids = []

    try:
        for i in range(sources_to_create):
            unique_id = uuid.uuid4().hex[:8]
            source_data = SourceCreate(
                name=f"Test Source {i}",
                short_name=f"test_source_{i}_{unique_id}",
                class_name="TestSourceConnector",
                auth_type=None,
                auth_config_class="TestAuthConfig",
                config_class="TestConfig",
                description=f"Test source {i} for get_all test",
                organization_id=None,
                output_entity_definition_ids=[],
                config_schema={"type": "object", "properties": {}},
            )

            created_source = await crud_source.create(db=db_session, obj_in=source_data)
            created_ids.append(created_source.id)

        # Act - Get all with default pagination
        all_sources = await crud_source.get_all(db=db_session)

        # Assert
        assert len(all_sources) >= sources_to_create

        # Check if our created sources are in the result
        created_sources_found = 0
        for source in all_sources:
            if source.id in created_ids:
                created_sources_found += 1

        assert created_sources_found == sources_to_create

        # Act - Test pagination (skip 2, limit 2)
        paginated_sources = await crud_source.get_all(db=db_session, skip=2, limit=2, disable_limit=False)

        # Assert
        assert len(paginated_sources) <= 2

    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise
