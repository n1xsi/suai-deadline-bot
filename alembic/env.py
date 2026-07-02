import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Импортируем конфигурацию проекта и метаданные моделей, чтобы Alembic знал, к какой БД подключаться и какую схему сравнивать
from src.config import DB_PATH
from src.database.models import Base

# Объект конфигурации Alembic, дающий доступ к значениям из alembic.ini
config = context.config

# URL к БД берём не из alembic.ini, а из общей конфигурации проекта.
# Так локальный запуск и запуск в Docker (через DB_PATH) используют одну логику.
config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{DB_PATH}")

# Настройка логирования из alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Метаданные моделей - цель для автогенерации миграций
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Запуск миграций в 'offline'-режиме (генерация SQL без подключения к БД).
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # SQLite не поддерживает полноценный ALTER TABLE - включаем batch-режим
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Создаёт асинхронный движок и выполняет миграции в рамках соединения.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Запуск миграций в 'online'-режиме (с реальным подключением к БД).
    """
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
