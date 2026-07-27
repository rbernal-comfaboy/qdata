"""add performance indexes

Revision ID: a3b4c5d6e7f8
Revises: f0e1d2c3b4a5
Create Date: 2026-07-27 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, None] = "f0e1d2c3b4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_group_permissions_user_id", "group_permissions", ["user_id"])
    op.create_index("ix_group_permissions_group_id", "group_permissions", ["group_id"])
    op.create_index("ix_projects_group_id", "projects", ["group_id"])
    op.create_index("ix_projects_user_id", "projects", ["user_id"])
    op.create_index("ix_reports_project_id", "reports", ["project_id"])
    op.create_index("ix_reports_user_id", "reports", ["user_id"])
    op.create_index("ix_reports_executed_at", "reports", ["executed_at"])
    op.create_index("ix_scheduled_tasks_project_id", "scheduled_tasks", ["project_id"])
    op.create_index("ix_data_sources_user_id", "data_sources", ["user_id"])
    op.create_index("ix_sources_user_id", "sources", ["user_id"])
    op.create_index("ix_sources_data_source_id", "sources", ["data_source_id"])
    op.create_index("ix_error_actions_report_id", "error_actions", ["report_id"])


def downgrade() -> None:
    op.drop_index("ix_error_actions_report_id", table_name="error_actions")
    op.drop_index("ix_sources_data_source_id", table_name="sources")
    op.drop_index("ix_sources_user_id", table_name="sources")
    op.drop_index("ix_data_sources_user_id", table_name="data_sources")
    op.drop_index("ix_scheduled_tasks_project_id", table_name="scheduled_tasks")
    op.drop_index("ix_reports_executed_at", table_name="reports")
    op.drop_index("ix_reports_user_id", table_name="reports")
    op.drop_index("ix_reports_project_id", table_name="reports")
    op.drop_index("ix_projects_user_id", table_name="projects")
    op.drop_index("ix_projects_group_id", table_name="projects")
    op.drop_index("ix_group_permissions_group_id", table_name="group_permissions")
    op.drop_index("ix_group_permissions_user_id", table_name="group_permissions")
