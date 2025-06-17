"""Add entity performance indexes

Revision ID: add_entity_perf_idx
Revises: b1170e606aae
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_entity_perf_idx'
down_revision = 'b1170e606aae'  # Points to the merge_multiple_heads migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add performance indexes to entity table."""
    # Create index on sync_id for faster filtering
    op.create_index(
        'idx_entity_sync_id',
        'entity',
        ['sync_id'],
        unique=False,
        postgresql_using='btree'
    )

    # Create index on sync_job_id for job-based queries
    op.create_index(
        'idx_entity_sync_job_id',
        'entity',
        ['sync_job_id'],
        unique=False,
        postgresql_using='btree'
    )

    # Create index on entity_id for lookups
    op.create_index(
        'idx_entity_entity_id',
        'entity',
        ['entity_id'],
        unique=False,
        postgresql_using='btree'
    )

    # Create composite index for the most common query pattern
    # This is used by get_by_entity_and_sync_id
    op.create_index(
        'idx_entity_entity_id_sync_id',
        'entity',
        ['entity_id', 'sync_id'],
        unique=False,
        postgresql_using='btree'
    )


def downgrade() -> None:
    """Remove the performance indexes."""
    op.drop_index('idx_entity_entity_id_sync_id', table_name='entity')
    op.drop_index('idx_entity_entity_id', table_name='entity')
    op.drop_index('idx_entity_sync_job_id', table_name='entity')
    op.drop_index('idx_entity_sync_id', table_name='entity')
