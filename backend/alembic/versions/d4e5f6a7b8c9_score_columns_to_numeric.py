"""change score columns to numeric(5,2)

Revision ID: d4e5f6a7b8c9
Revises: b2c3d4e5f6a7
Create Date: 2026-09-02 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    score_type = sa.Numeric(5, 2)
    op.alter_column('reports', 'score', existing_type=sa.Integer(), type_=score_type,
                    existing_nullable=True, postgresql_using='score::numeric(5,2)')
    op.alter_column('task_history', 'score', existing_type=sa.Integer(), type_=score_type,
                    existing_nullable=True, postgresql_using='score::numeric(5,2)')


def downgrade() -> None:
    op.alter_column('task_history', 'score', existing_type=sa.Numeric(5, 2), type_=sa.Integer(),
                    existing_nullable=True, postgresql_using='score::integer')
    op.alter_column('reports', 'score', existing_type=sa.Numeric(5, 2), type_=sa.Integer(),
                    existing_nullable=True, postgresql_using='score::integer')
