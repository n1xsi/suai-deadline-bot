"""undated deadlines

Revision ID: 0002_undated_deadlines
Revises: 0001_initial_schema
Create Date: 2026-09-27 12:00:00.000000+03:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Идентификаторы ревизии, используемые Alembic.
revision: str = "0002_undated_deadlines"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# SQLite не умеет менять nullability через ALTER TABLE, поэтому Alembic пересоздаёт таблицу
# в batch-режиме. Схема описывается явно (copy_from), чтобы не зависеть от рефлексии
DEADLINES_BEFORE = sa.Table(
    "deadlines",
    sa.MetaData(),
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("user_id", sa.Integer(), nullable=False),
    sa.Column("course_name", sa.String(length=100), nullable=False),
    sa.Column("task_name", sa.String(length=255), nullable=False),
    sa.Column("due_date", sa.DateTime(), nullable=False),
    sa.Column("is_custom", sa.Boolean(), server_default="false", nullable=False),
    sa.Column("is_trashed", sa.Boolean(), server_default="false", nullable=False),
    sa.PrimaryKeyConstraint("id"),
)

DEADLINES_AFTER = sa.Table(
    "deadlines",
    sa.MetaData(),
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("user_id", sa.Integer(), nullable=False),
    sa.Column("course_name", sa.String(length=100), nullable=False),
    sa.Column("task_name", sa.String(length=255), nullable=False),
    sa.Column("due_date", sa.DateTime(), nullable=True),
    sa.Column("is_custom", sa.Boolean(), server_default="false", nullable=False),
    sa.Column("is_trashed", sa.Boolean(), server_default="false", nullable=False),
    # Колонки, добавленные в upgrade(), дописываются в конец таблицы
    sa.Column("task_url", sa.String(length=512), nullable=True),
    sa.Column("is_user_dated", sa.Boolean(), server_default="false", nullable=False),
    sa.PrimaryKeyConstraint("id"),
)


def upgrade() -> None:
    # В ЛК ГУАП часть заданий не имеет предельной даты: такие дедлайны теперь хранятся
    # с due_date = NULL, ссылкой на задание и признаком "срок выставил сам пользователь"
    with op.batch_alter_table("deadlines", copy_from=DEADLINES_BEFORE) as batch_op:
        batch_op.alter_column("due_date", existing_type=sa.DateTime(), nullable=True)
        batch_op.add_column(sa.Column("task_url", sa.String(length=512), nullable=True))
        batch_op.add_column(
            sa.Column(
                "is_user_dated",
                sa.Boolean(),
                server_default="false",
                nullable=False,
            )
        )


def downgrade() -> None:
    # В старой схеме дедлайн без срока сдачи существовать не может - такие записи удаляются
    op.execute("DELETE FROM deadlines WHERE due_date IS NULL")

    with op.batch_alter_table("deadlines", copy_from=DEADLINES_AFTER) as batch_op:
        batch_op.drop_column("is_user_dated")
        batch_op.drop_column("task_url")
        batch_op.alter_column("due_date", existing_type=sa.DateTime(), nullable=False)
