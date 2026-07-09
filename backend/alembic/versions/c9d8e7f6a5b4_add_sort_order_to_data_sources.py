"""add sort_order to data_sources

Revision ID: c9d8e7f6a5b4
Revises: b3c4d5e6f7a8
Create Date: 2026-07-09 16:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c9d8e7f6a5b4'
down_revision: Union[str, None] = 'd1b1dca7ca7f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('data_sources', sa.Column('sort_order', sa.Integer(), nullable=True, server_default=sa.text('0')))


def downgrade() -> None:
    op.drop_column('data_sources', 'sort_order')
