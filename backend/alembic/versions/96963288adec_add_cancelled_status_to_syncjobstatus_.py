"""Add CANCELLED status to SyncJobStatus enum

Revision ID: 96963288adec
Revises: 18a5f5a5e8a1
Create Date: 2024-01-10 17:20:46.123456

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '96963288adec'
down_revision: Union[str, None] = 'add_entity_perf_idx'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add CANCELLED to syncjobstatus enum."""
    # PostgreSQL requires special handling for enum types
    op.execute("ALTER TYPE syncjobstatus ADD VALUE IF NOT EXISTS 'cancelled'")


def downgrade() -> None:
    """Remove CANCELLED from syncjobstatus enum.

    Note: PostgreSQL doesn't support removing values from enums easily.
    This would require recreating the entire enum and all columns using it.
    """
    # For safety, we'll just pass here. In production, you'd need a more complex migration.
    pass
