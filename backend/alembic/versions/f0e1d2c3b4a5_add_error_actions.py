"""add error_actions table

Revision ID: f0e1d2c3b4a5
Revises: e5f6a7b8c9d0
Create Date: 2026-07-17 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = 'f0e1d2c3b4a5'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'error_actions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('report_id', UUID(as_uuid=True), sa.ForeignKey('reports.id', ondelete='CASCADE'), nullable=False),
        sa.Column('rule_index', sa.Integer(), nullable=False),
        sa.Column('error_index', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='sin_accion'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('report_id', 'rule_index', 'error_index', name='uq_error_action'),
    )


def downgrade() -> None:
    op.drop_table('error_actions')
