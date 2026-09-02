"""add rule_configs to projects

Revision ID: b2c3d4e5f6a7
Revises: f0e1d2c3b4a5
Create Date: 2026-08-11 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'c0d1e2f3a4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('rule_configs', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('projects', 'rule_configs')
