"""Add status and progress to projects

Revision ID: a1b2c3d4e5f6
Revises: 7f632d1bd76e
Create Date: 2026-06-04 20:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '7f632d1bd76e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('status', sa.String(length=20), nullable=True))
    op.add_column('projects', sa.Column('progress', sa.JSON(), nullable=True))
    op.execute("UPDATE projects SET status = 'completed' WHERE status IS NULL")


def downgrade() -> None:
    op.drop_column('projects', 'progress')
    op.drop_column('projects', 'status')
