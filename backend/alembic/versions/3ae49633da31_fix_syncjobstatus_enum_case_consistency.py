"""fix_syncjobstatus_enum_case_consistency

Revision ID: 3ae49633da31
Revises: 96963288adec
Create Date: 2025-06-10 18:12:00.951662

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3ae49633da31'
down_revision = '96963288adec'
branch_labels = None
depends_on = None


def upgrade():
    """Add CANCELLED (uppercase) to syncjobstatus enum to match existing case pattern.

    The database currently has mixed case:
    - PENDING, IN_PROGRESS, COMPLETED, FAILED (uppercase)
    - cancelled (lowercase)

    We need CANCELLED (uppercase) to match the pattern used by existing values.
    """
    # Add the uppercase CANCELLED value
    op.execute("ALTER TYPE syncjobstatus ADD VALUE IF NOT EXISTS 'CANCELLED'")


def downgrade():
    """Remove CANCELLED from syncjobstatus enum.

    Note: PostgreSQL doesn't support removing values from enums easily.
    This would require recreating the entire enum and all columns using it.
    """
    # For safety, we'll just pass here. In production, you'd need a more complex migration.
    pass
