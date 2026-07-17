"""add group_permissions table

Revision ID: e5f6a7b8c9d0
Revises: c9d8e7f6a5b4
Create Date: 2026-07-16 16:50:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'c9d8e7f6a5b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'group_permissions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('group_id', UUID(as_uuid=True), sa.ForeignKey('analysis_groups.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'group_id', name='uq_user_group_permission'),
    )


def downgrade() -> None:
    op.drop_table('group_permissions')
