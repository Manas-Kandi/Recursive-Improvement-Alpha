"""add_action_templates_and_template_set

Revision ID: a1f2e3d4c5b6
Revises: bdfabafa9f67, e3a4b5c6d7e8
Create Date: 2026-06-09 16:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'a1f2e3d4c5b6'
down_revision: Union[str, Sequence[str], None] = ('bdfabafa9f67', 'e3a4b5c6d7e8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: create actiontemplate table and harnessversion.template_set."""
    op.create_table(
        'actiontemplate',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('pattern', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('tool_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('args_template', sa.JSON(), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('example', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='active'),
        sa.Column('origin', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='seed'),
        sa.Column('version', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='1.0.0'),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('source_task_id', sa.Integer(), nullable=True),
        sa.Column('hit_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_ts', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_actiontemplate_name'), 'actiontemplate', ['name'], unique=False)
    op.add_column('harnessversion', sa.Column('template_set', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('harnessversion', 'template_set')
    op.drop_index(op.f('ix_actiontemplate_name'), table_name='actiontemplate')
    op.drop_table('actiontemplate')
