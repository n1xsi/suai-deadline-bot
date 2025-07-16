from sqlalchemy import select, update, delete, func
from datetime import datetime, timedelta

from src.database.engine import async_session_factory
from src.database.models import User, Deadline
from src.utils.crypto import encrypt_data, decrypt_data


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
        

async def get_all_users():
    """Возвращает список всех зарегистрированных пользователей."""
    async with async_session_factory() as session:
        result = await session.execute(select(User))
        return result.scalars().all()

async def get_user_by_telegram_id(telegram_id: int):
    """Возвращает пользователя по его telegram_id."""
    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalars().first()

async def update_user_deadlines(telegram_id: int, new_deadlines: list[dict]):
    """Удаляет все старые дедлайны пользователя и записывает новые."""
    async with async_session_factory() as session:
        # Находим id пользователя в БД
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            return

        # Удаляем все его старые дедлайны
        await session.execute(delete(Deadline).where(Deadline.user_id == user.id))
        
        # Добавляем новые дедлайны
        deadline_objects = []
        for d in new_deadlines:
            # Преобразуем строку с датой в объект datetime
            # Формат даты в ЛК: "ДД.ММ.ГГГГ".
            try:
                due_date_obj = datetime.strptime(d['due_date'], "%d.%m.%Y")
            except ValueError:
                # Пропускаем дедлайн, если формат даты некорректный
                continue

            deadline_objects.append(
                Deadline(
                    user_id=user.id,
                    course_name=d['subject'],
                    task_name=d['task'],
                    due_date=due_date_obj
                )
            )
        
        session.add_all(deadline_objects)
        await session.commit()

async def get_users_with_upcoming_deadlines(days: int):
    """
    Находит пользователей, у которых дедлайн наступает ровно через `days` дней.
    """
    async with async_session_factory() as session:
        target_date = datetime.now().date() + timedelta(days=days)
        
        # Находим дедлайны, которые наступают в целевую дату
        # и присоединяем информацию о пользователях
        query = (
            select(User, Deadline)
            .join(Deadline, User.id == Deadline.user_id)
            .where(func.date(Deadline.due_date) == target_date)
        )
        result = await session.execute(query)
        return result.all() # Возвращаем пары (User, Deadline)