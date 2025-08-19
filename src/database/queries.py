from datetime import datetime, timedelta

from sqlalchemy import select, update, delete, func

from src.database.engine import async_session_factory
from src.database.models import User, Deadline
from src.utils.crypto import encrypt_data


async def add_user(telegram_id: int, username: str | None = None):
    """
    Функция для добавления нового пользователя в БД.
    Возвращает True, если пользователь был добавлен, False - если уже существует.
    """
    async with async_session_factory() as session:
        # Проверка, есть ли уже пользователь с таким telegram_id
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        if result.scalars().first():
            return False  # Пользователь уже существует

        # Такого пользователя нет - нужно добавить
        new_user = User(telegram_id=telegram_id, username=username)
        session.add(new_user)
        await session.commit()
        return True


async def set_user_credentials(telegram_id: int, login: str, password: str):
    """Шифрует и сохраняет логин/пароль пользователя в БД."""
    async with async_session_factory() as session:
        encrypted_login = encrypt_data(login)
        encrypted_password = encrypt_data(password)

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


async def get_all_users(only_with_notifications: bool = False):
    """
    Возвращает список всех зарегистрированных пользователей.
    only_with_notifications=True - только тех, у кого включены уведомления.
    """
    async with async_session_factory() as session:
        query = select(User)
        if only_with_notifications:
            query = query.where(User.notifications_enabled == True)
        result = await session.execute(query)
        return result.scalars().all()


async def get_user_by_telegram_id(telegram_id: int):
    """Возвращает пользователя по его telegram_id."""
    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalars().first()


async def update_user_deadlines(telegram_id: int, new_parsed_deadlines: list[dict]):
    """
    "Умно" синхронизирует дедлайны из парсера с базой данных.
    Не трогает дедлайны, добавленные вручную.
    """
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            return

        # Поиск всех существующих "парсерных" дедлайнов из БД
        existing_deadlines_query = await session.execute(
            select(Deadline).where(Deadline.user_id ==user.id, Deadline.is_custom == False)
        )
        existing_deadlines_list = existing_deadlines_query.scalars().all()

        # Создание множества существующих дедлайнов для быстрой проверки (ключ - предмет+задание)
        existing_deadlines_set = {
            (d.course_name, d.task_name): d for d in existing_deadlines_list
        }

        # Создание множества новых дедлайнов из парсера
        parsed_deadlines_set = {
            (d['subject'], d['task']): d for d in new_parsed_deadlines
        }

        # Поиск дедлайнов, которые нужно УДАЛИТЬ
        # (те, что есть в БД, но которых нет в новом списке из парсера)
        to_delete_ids = [
            existing_deadlines_set[key].id
            for key in existing_deadlines_set
            if key not in parsed_deadlines_set
        ]
        if to_delete_ids:
            await session.execute(delete(Deadline).where(Deadline.id.in_(to_delete_ids)))

        # Поиск дедлайнов, которые нужно ДОБАВИТЬ
        # (те, что есть в новом списке, но которых нет в БД)
        to_add_objects = []
        for key, data in parsed_deadlines_set.items():
            if key not in existing_deadlines_set:
                try:
                    due_date_obj = datetime.strptime(data['due_date'], "%d.%m.%Y")
                except ValueError:
                    continue
                to_add_objects.append(
                    Deadline(
                        user_id=user.id,
                        course_name=data['subject'],
                        task_name=data['task'],
                        due_date=due_date_obj,
                        is_custom=False
                    )
                )
        if to_add_objects:
            session.add_all(to_add_objects)

        await session.commit()


async def get_users_with_upcoming_deadlines(days: int):
    """
    Находит пользователей, у которых дедлайн наступает ровно через `days` дней.
    """
    async with async_session_factory() as session:
        target_date = datetime.now().date() + timedelta(days=days)

        # Поиск дедлайнов, которые наступают в целевую дату и присоединение информации о пользователях
        query = (
            select(User, Deadline)
            .join(Deadline, User.id == Deadline.user_id)
            .where(func.date(Deadline.due_date) == target_date)
        )
        result = await session.execute(query)
        return result.all()  # Возврат пары (User, Deadline)


async def get_user_stats(telegram_id: int) -> dict:
    """Возвращает статистику по пользователю."""
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            return {}

        # Подсчёт активных дедлайнов
        query = select(func.count(Deadline.id)).where(
            Deadline.user_id == user.id,
            Deadline.due_date >= datetime.now().date()
        )
        active_deadlines_count = await session.execute(query)

        return {
            "active_deadlines": active_deadlines_count.scalar_one_or_none() or 0,
        }


async def delete_user_data(telegram_id: int):
    """Полностью удаляет пользователя и все его данные из БД."""
    async with async_session_factory() as session:
        user_query = select(User).where(User.telegram_id == telegram_id)
        user_result = await session.execute(user_query)
        user = user_result.scalars().first()

        if user:
            # Удаление связанных дедлайнов
            await session.execute(delete(Deadline).where(Deadline.user_id == user.id))
            # Затем удаление пользователя
            await session.execute(delete(User).where(User.telegram_id == telegram_id))
            await session.commit()
            return True
    return False


async def get_user_deadlines_from_db(telegram_id: int):
    """Получает все актуальные дедлайны пользователя из БД."""
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            return []

        # Поиск дедлайнов, которые ещё не прошли
        query = (
            select(Deadline)
            .where(Deadline.user_id == user.id, Deadline.due_date >= datetime.now().date())
            .order_by(Deadline.due_date.asc())
        )
        result = await session.execute(query)
        return result.scalars().all()


async def add_custom_deadline(telegram_id: int, course: str, task: str, due_date: datetime):
    """Добавляет один личный дедлайн для пользователя."""
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            return None

        new_deadline = Deadline(
            user_id=user.id,
            course_name=course,
            task_name=task,
            due_date=due_date,
            is_custom=True
        )
        session.add(new_deadline)
        await session.commit()
        return new_deadline
    

async def get_deadline_by_id(deadline_id: int):
    """Возвращает объект дедлайна по его ID."""
    async with async_session_factory() as session:
        query = select(Deadline).where(Deadline.id == deadline_id)
        result = await session.execute(query)
        return result.scalars().first()


async def delete_deadline_by_id(deadline_id: int):
    """Удаляет дедлайн по его ID."""
    async with async_session_factory() as session:
        query = delete(Deadline).where(Deadline.id == deadline_id)
        await session.execute(query)
        await session.commit()


async def toggle_notifications(telegram_id: int) -> bool:
    """Включает/выключает уведомления для пользователя и возвращает новое состояние."""
    async with async_session_factory() as session:
        user_result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user_result.scalars().first()
        if not user:
            return False

        user.notifications_enabled = not user.notifications_enabled
        new_state = user.notifications_enabled
        await session.commit()
        return new_state


async def update_notification_days(telegram_id: int, day: int) -> str:
    """Добавляет или убирает день из списка уведомлений."""
    async with async_session_factory() as session:
        user_result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user_result.scalars().first()
        if not user:
            return ""

        if user.notification_days:
            days_set = set(map(int, user.notification_days.split(',')))
        else:
            days_set = set()

        if day in days_set:
            days_set.remove(day)
        else:
            days_set.add(day)

        new_days_list = sorted(list(days_set))
        user.notification_days = ",".join(map(str, new_days_list))
        new_days_str = user.notification_days
        await session.commit()
        return new_days_str


async def set_notification_interval(telegram_id: int, hours: int):
    """Устанавливает интервал частых уведомлений для пользователя."""
    async with async_session_factory() as session:
        query = (
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(notification_interval_hours=hours)
        )
        await session.execute(query)
        await session.commit()
