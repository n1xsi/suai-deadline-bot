from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from src.config import DB_PATH

# Асинхронный "движок" для подключения к SQLite-БД
engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}")

# Фабрика сессий, через которую происходит взаимодействие с БД
async_session_factory = async_sessionmaker(engine)
