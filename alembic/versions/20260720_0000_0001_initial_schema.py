"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-20 00:00:00.000000+03:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Идентификаторы ревизии, используемые Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=32), nullable=True),
        sa.Column("profile_id", sa.Integer(), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("encrypted_login_lk", sa.String(length=255), nullable=True),
        sa.Column("encrypted_password_lk", sa.String(length=255), nullable=True),
        sa.Column(
            "notifications_enabled",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.Column(
            "notification_days",
            sa.String(),
            server_default="1,3,7",
            nullable=False,
        ),
        sa.Column(
            "notification_interval_hours",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_id"),
    )
    op.create_table(
        "deadlines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("course_name", sa.String(length=100), nullable=False),
        sa.Column("task_name", sa.String(length=255), nullable=False),
        sa.Column("due_date", sa.DateTime(), nullable=False),
        sa.Column(
            "is_custom", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column(
            "is_trashed", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("deadlines")
    op.drop_table("users")
