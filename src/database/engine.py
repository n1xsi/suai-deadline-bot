from loguru import logger
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from src.config import DB_PATH
from src.database.models import Base

# Асинхронный "движок" для подключения к SQLite-БД
# "echo" - выводит в консоль все SQL-запросы
engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}")

# Фабрика сессий, через которую происходит взаимодействие с БД
async_session_factory = async_sessionmaker(engine)


async def create_tables():
    """
    Функция для создания таблиц в БД на основе моделей
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.success("Таблицы базы данных созданы/проверены")


async def delete_tables():
    """
    Функция для удаления таблиц (для тестов)
    """
    async with engine.begin() as conn:
        logger.warning("Таблицы базы данных удалены")
        await conn.run_sync(Base.metadata.drop_all)
