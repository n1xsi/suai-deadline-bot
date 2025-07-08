from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from src.config import DB_PATH
from src.database.models import Base

# Асинхронный "движок" для подключения к SQLite-БД
engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}", echo=True) # "echo" выводит в консоль все SQL-запросы

# Фабрика сессий, через которую будем взаимодействовать с БД
async_session_factory = async_sessionmaker(engine)

async def create_tables():
    """
    Функция для создания таблиц в БД на основе наших моделей
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def delete_tables():
    """
    Функция для удаления таблиц (для тестов)
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)