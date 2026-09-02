"""add rule_totals column to reports

Revision ID: c0d1e2f3a4b5
Revises: a3b4c5d6e7f8
Create Date: 2026-08-03 14:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c0d1e2f3a4b5"
down_revision: Union[str, None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("reports", sa.Column("rule_totals", sa.JSON(), nullable=True))
    op.execute(
        """
        UPDATE reports
        SET rule_totals = sub.totals
        FROM (
            SELECT r2.id, (
                SELECT jsonb_agg(jsonb_build_object(
                    'rule_name', rule.value->>'rule_name',
                    'passed', COALESCE(
                        (rule.value->>'passed')::boolean,
                        (rule.value->>'pass')::boolean,
                        false
                    ),
                    'failed', (rule.value->>'failed')::int,
                    'total', (rule.value->>'total')::int,
                    'severity', rule.value->>'severity'
                ))
                FROM jsonb_array_elements(r2.result_json::jsonb->'results') AS rule
            ) AS totals
            FROM reports r2
            WHERE r2.result_json IS NOT NULL
        ) sub
        WHERE reports.id = sub.id
        """
    )


def downgrade() -> None:
    op.drop_column("reports", "rule_totals")
