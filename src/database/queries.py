from sqlalchemy import select
from src.database.engine import async_session_factory
from src.database.models import User

async def add_user(telegram_id: int, username: str | None = None):
    """
    Функция для добавления нового пользователя в БД.
    Возвращает True, если пользователь был добавлен, False - если уже существует.
    """
    async with async_session_factory() as session:
        # Проверяем, есть ли уже пользователь с таким telegram_id
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        if result.scalars().first():
            return False # Пользователь уже существует

        # Такого пользователя нет - добавляем его
        new_user = User(telegram_id=telegram_id, username=username)
        session.add(new_user)
        await session.commit()
        return True