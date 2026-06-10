"""add_template_trust_counters_and_task_triage

Revision ID: b7c8d9e0f1a2
Revises: a1f2e3d4c5b6
Create Date: 2026-06-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, Sequence[str], None] = 'a1f2e3d4c5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add graduated-trust counters to actiontemplate and triage to task."""
    op.add_column('actiontemplate', sa.Column('success_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('actiontemplate', sa.Column('failure_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('task', sa.Column('triage', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('task', 'triage')
    op.drop_column('actiontemplate', 'failure_count')
    op.drop_column('actiontemplate', 'success_count')
