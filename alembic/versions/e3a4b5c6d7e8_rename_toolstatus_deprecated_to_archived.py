"""rename_toolstatus_deprecated_to_archived

Revision ID: e3a4b5c6d7e8
Revises: c08fb9266eb4
Create Date: 2026-06-08 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3a4b5c6d7e8'
down_revision: Union[str, Sequence[str], None] = 'c08fb9266eb4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite does not support ALTER on enum columns directly.
    # For SQLite we recreate the table; for other engines a simple ALTER works.
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        # SQLite: recreate the enum type via batch alter
        with op.batch_alter_table('tool') as batch_op:
            batch_op.alter_column(
                'status',
                type_=sa.Enum('active', 'archived', name='toolstatus'),
                existing_type=sa.Enum('active', 'deprecated', name='toolstatus'),
                existing_nullable=False,
            )
    else:
        op.alter_column(
            'tool',
            'status',
            type_=sa.Enum('active', 'archived', name='toolstatus'),
            existing_type=sa.Enum('active', 'deprecated', name='toolstatus'),
            existing_nullable=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        with op.batch_alter_table('tool') as batch_op:
            batch_op.alter_column(
                'status',
                type_=sa.Enum('active', 'deprecated', name='toolstatus'),
                existing_type=sa.Enum('active', 'archived', name='toolstatus'),
                existing_nullable=False,
            )
    else:
        op.alter_column(
            'tool',
            'status',
            type_=sa.Enum('active', 'deprecated', name='toolstatus'),
            existing_type=sa.Enum('active', 'archived', name='toolstatus'),
            existing_nullable=False,
        )
