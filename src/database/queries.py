from sqlalchemy import select, update
from src.database.engine import async_session_factory
from src.database.models import User, Deadline
from src.utils.crypto import encrypt_data

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

async def set_user_credentials(telegram_id: int, login: str, password: str):
    """Шифрует и сохраняет логин/пароль пользователя в БД."""
    async with async_session_factory() as session:
        # Шифруем данные перед записью
        encrypted_login = encrypt_data(login)
        encrypted_password = encrypt_data(password)

        # Создаем запрос на обновление
        query = (
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(
                encrypted_login_lk=encrypted_login,
                encrypted_password_lk=encrypted_password
            )
        )
        await session.execute(query)
        await session.commit()