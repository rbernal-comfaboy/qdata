"""add missing source columns

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-06-19 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sources', sa.Column('selected_columns', sa.JSON(), nullable=True, server_default=sa.text("'[]'::json")))
    op.add_column('sources', sa.Column('row_limit', sa.Integer(), nullable=True))
    op.add_column('sources', sa.Column('storage_mode', sa.String(length=20), nullable=True, server_default='connection'))
    op.add_column('sources', sa.Column('refresh_cron', sa.String(length=100), nullable=True))
    op.add_column('sources', sa.Column('refresh_enabled', sa.Boolean(), nullable=True, server_default=sa.text('false')))


def downgrade() -> None:
    op.drop_column('sources', 'refresh_enabled')
    op.drop_column('sources', 'refresh_cron')
    op.drop_column('sources', 'storage_mode')
    op.drop_column('sources', 'row_limit')
    op.drop_column('sources', 'selected_columns')
