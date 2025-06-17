"""remove_lowercase_cancelled_enum_value

Revision ID: 94cba0badfd8
Revises: 3ae49633da31
Create Date: 2025-06-10 18:18:09.123456

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '94cba0badfd8'
down_revision = '3ae49633da31'
branch_labels = None
depends_on = None


def upgrade():
    """Remove the lowercase 'cancelled' value from syncjobstatus enum.

    PostgreSQL doesn't support removing enum values directly, so we need to:
    1. Create a new enum type with only the correct values
    2. Convert the column to use the new enum type
    3. Drop the old enum type
    4. Rename the new enum type to the original name
    """

    # Step 1: Create new enum type with only uppercase values
    op.execute("""
        CREATE TYPE syncjobstatus_new AS ENUM (
            'PENDING',
            'IN_PROGRESS',
            'COMPLETED',
            'FAILED',
            'CANCELLED'
        )
    """)

    # Step 2: Convert the sync_job table column to use the new enum
    # First convert to text, then to the new enum
    op.execute("""
        ALTER TABLE sync_job
        ALTER COLUMN status TYPE text
    """)

    # Update any potential lowercase 'cancelled' values to uppercase
    op.execute("""
        UPDATE sync_job
        SET status = 'CANCELLED'
        WHERE status = 'cancelled'
    """)

    # Convert to the new enum type
    op.execute("""
        ALTER TABLE sync_job
        ALTER COLUMN status TYPE syncjobstatus_new
        USING status::syncjobstatus_new
    """)

    # Step 3: Drop the old enum type
    op.execute("DROP TYPE syncjobstatus")

    # Step 4: Rename the new enum type to the original name
    op.execute("ALTER TYPE syncjobstatus_new RENAME TO syncjobstatus")


def downgrade():
    """Recreate the enum with both cancelled values.

    This restores the previous state with both 'cancelled' and 'CANCELLED'.
    """

    # Create the old enum type with both values
    op.execute("""
        CREATE TYPE syncjobstatus_old AS ENUM (
            'PENDING',
            'IN_PROGRESS',
            'COMPLETED',
            'FAILED',
            'cancelled',
            'CANCELLED'
        )
    """)

    # Convert column
    op.execute("""
        ALTER TABLE sync_job
        ALTER COLUMN status TYPE text
    """)

    op.execute("""
        ALTER TABLE sync_job
        ALTER COLUMN status TYPE syncjobstatus_old
        USING status::syncjobstatus_old
    """)

    # Drop and rename
    op.execute("DROP TYPE syncjobstatus")
    op.execute("ALTER TYPE syncjobstatus_old RENAME TO syncjobstatus")
