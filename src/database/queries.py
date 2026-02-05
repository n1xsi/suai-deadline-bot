from datetime import datetime, timedelta
from typing import Optional, List, Dict

from loguru import logger
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
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        if result.scalars().first():
            logger.warning(f"Пользователь с telegram_id={telegram_id} уже существует")
            return False

        new_user = User(telegram_id=telegram_id, username=username)
        session.add(new_user)
        await session.commit()
        logger.success(f"Пользователь с telegram_id={telegram_id} добавлен")
        return True


async def set_user_credentials(
    telegram_id: int,
    login: str,
    password: str,
    profile_id: Optional[str] = None,
    full_name: Optional[str] = None
):
    """Шифрует и сохраняет учётные данные, ID профиля и ФИО пользователя в БД."""
    async with async_session_factory() as session:
        encrypted_login = encrypt_data(login)
        encrypted_password = encrypt_data(password)

        query = (
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(
                encrypted_login_lk=encrypted_login,
                encrypted_password_lk=encrypted_password,
                profile_id=int(profile_id) if profile_id else None,
                full_name=full_name
            )
        )
        await session.execute(query)
        await session.commit()
        logger.success(f"Пользователь с telegram_id={telegram_id} обновлен")


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
        logger.success("Пользователи получены")
        return result.scalars().all()


async def get_user_by_telegram_id(telegram_id: int):
    """Возвращает пользователя по его telegram_id."""
    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        logger.success(f"Пользователь с telegram_id={telegram_id} получен")
        return result.scalars().first()


async def update_user_deadlines(telegram_id: int, new_parsed_deadlines: list[dict]) -> List[Dict]:
    """
    "Умно" синхронизирует дедлайны из парсера с базой данных, не трогая дедлайны, добавленные вручную.
    Возвращает список словарей с данными о вновь добавленных дедлайнах.
    """
    # TODO: Разбить на несколько функций
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            return []

        # Получаение всех существующих "парсерных" дедлайнов из БД (не личных)
        existing_deadlines_query = await session.execute(
            select(Deadline).where(Deadline.user_id == user.id, Deadline.is_custom == False)
        )
        existing_deadlines_list = existing_deadlines_query.scalars().all()

        # Создание множества для быстрой проверки (ключ - предмет+задание)
        existing_deadlines_set = {
            (d.course_name, d.task_name): d for d in existing_deadlines_list
        }
        parsed_deadlines_set = {
            (d['subject'], d['task']): d for d in new_parsed_deadlines
        }

        # Поиск дедлайнов, которые нужно удалить (ЕСТЬ в БД, но НЕТ в парсере)
        to_delete_ids = [
            existing_deadlines_set[key].id
            for key in existing_deadlines_set
            if key not in parsed_deadlines_set
        ]
        if to_delete_ids:
            await session.execute(delete(Deadline).where(Deadline.id.in_(to_delete_ids)))

        # Поиск и создание дедлайнов, которые нужно добавить
        newly_added_deadlines_data = []
        objects_to_add_in_db = []

        for key, data in parsed_deadlines_set.items():
            if key not in existing_deadlines_set:
                try:
                    due_date_obj = datetime.strptime(data['due_date'], "%d.%m.%Y")
                except ValueError:
                    continue

                # Сохранение данных о новом дедлайне
                newly_added_deadlines_data.append({
                    'course_name': data['subject'],
                    'task_name': data['task'],
                    'due_date': due_date_obj
                })

                # Создание объекта для добавления в БД
                objects_to_add_in_db.append(
                    Deadline(
                        user_id=user.id,
                        course_name=data['subject'],
                        task_name=data['task'],
                        due_date=due_date_obj,
                        is_custom=False
                    )
                )

        if objects_to_add_in_db:
            session.add_all(objects_to_add_in_db)

        await session.commit()
        logger.success(f'Добавлено {len(objects_to_add_in_db)} дедлайнов') 
        return newly_added_deadlines_data


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
        data = result.all()
        logger.success(f'Пользователи с дедлайнами наступающими в {days} дней: {len(data)}')
        return result.all()  # Возврат пары (User, Deadline)


async def get_user_stats(telegram_id: int) -> dict:
    """Возвращает статистику пользователя по telegram_id"""
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            logger.error(f'Не удалось получить статистику пользователя с telegram_id={telegram_id}, пользователя не существует')
            return {}

        # Подсчёт всех дедлайнов
        all_active_query = select(func.count(Deadline.id)).where(
            Deadline.user_id == user.id,
            Deadline.due_date >= datetime.now().date()
        )
        all_active_count = await session.execute(all_active_query)

        # Подсчёт личных дедлайнов
        custom_active_query = select(func.count(Deadline.id)).where(
            Deadline.user_id == user.id,
            Deadline.due_date >= datetime.now().date(),
            Deadline.is_custom == True
        )
        custom_active_count = await session.execute(custom_active_query)
        
        active_count = all_active_count.scalar_one_or_none() or 0
        custom_count = custom_active_count.scalar_one_or_none() or 0

        logger.success(f'Статистика пользователя {telegram_id}: {active_count} активных дедлайнов, {custom_count} личных')

        return {
            "active_deadlines": active_count,
            "custom_deadlines": custom_count
        }


async def delete_user_data(telegram_id: int) -> bool:
    """Полностью удаляет пользователя и все его данные из БД."""
    async with async_session_factory() as session:
        user_query = select(User).where(User.telegram_id == telegram_id)
        user_result = await session.execute(user_query)
        user = user_result.scalars().first()

        if user:
            # Удаление связанных дедлайнов
            await session.execute(delete(Deadline).where(Deadline.user_id == user.id))
            # Удаление пользователя
            await session.execute(delete(User).where(User.telegram_id == telegram_id))
            await session.commit()
            logger.success(f'Пользователь с telegram_id={telegram_id} удалён')
            return True
    logger.error(f'Не удалось удалить пользователя с telegram_id={telegram_id}')
    return False


async def get_user_deadlines_from_db(telegram_id: int) -> list[Deadline]:
    """Получает все актуальные дедлайны пользователя из БД."""
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            logger.error(f'Не удалось получить дедлайны пользователя с telegram_id={telegram_id}, пользователя не существует')
            return []

        # Поиск дедлайнов, которые ещё не прошли
        query = (
            select(Deadline)
            .where(
                Deadline.user_id == user.id,
                Deadline.due_date >= datetime.now().date(),
                Deadline.is_trashed == False
                )
            .order_by(Deadline.due_date.asc())
        )
        result = await session.execute(query)
        deadlines = result.scalars().all()
        logger.success(f'Пользователь с telegram_id={telegram_id} имеет {len(deadlines)} дедлайнов')
        return list(deadlines)


async def add_custom_deadline(telegram_id: int, course: str, task: str, due_date: datetime):
    """Добавляет один личный дедлайн для пользователя."""
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            logger.error(f'Не удалось добавить личный дедлайн для пользователя с telegram_id={telegram_id}, пользователя не существует')
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
        logger.success(f'Добавлен личный дедлайн для пользователя с telegram_id={telegram_id}')
        return new_deadline


async def get_deadline_by_id(deadline_id: int):
    """Возвращает объект дедлайна по его ID."""
    async with async_session_factory() as session:
        query = select(Deadline).where(Deadline.id == deadline_id)
        result = await session.execute(query)
        logger.success(f"Получен дедлайн с id={deadline_id}")
        return result.scalars().first()


async def move_deadline_to_trash(deadline_id: int):
    """Перемещает дедлайн в корзину (устанавливает is_trashed = True)."""
    async with async_session_factory() as session:
        query = (
            update(Deadline)
            .where(Deadline.id == deadline_id)
            .values(is_trashed=True)
        )
        await session.execute(query)
        await session.commit()
        logger.success(f'Дедлайн с id={deadline_id} перемещён в корзину')


async def toggle_notifications(telegram_id: int) -> bool:
    """Включает/выключает уведомления для пользователя и возвращает новое состояние."""
    async with async_session_factory() as session:
        user_result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user_result.scalars().first()
        if not user:
            logger.error(f"Не удалось переключить уведомления для пользователя с telegram_id={telegram_id}, пользователь не существует")
            return False

        user.notifications_enabled = not user.notifications_enabled
        new_state = user.notifications_enabled
        await session.commit()
        logger.success(f"Пользователь с telegram_id={telegram_id} переключил уведомления на {new_state}")
        return new_state


async def update_notification_days(telegram_id: int, day: int) -> str:
    """Добавляет или убирает день из списка уведомлений."""
    async with async_session_factory() as session:
        user_result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user_result.scalars().first()
        if not user:
            logger.error(f"Не удалось обновить уведомления для пользователя с telegram_id={telegram_id}, пользователь не существует")
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
        logger.success(f"Пользователь с telegram_id={telegram_id} обновил уведомления на {new_days_str}")
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
        logger.success(f"Пользователь с telegram_id={telegram_id} обновил интервал уведомлений на {hours} часов")


async def delete_all_custom_deadlines(telegram_id: int):
    """Удаляет ВСЕ личные (is_custom=True) дедлайны пользователя."""
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            logger.error(f"Не удалось удалить все личные дедлайны пользователя с telegram_id={telegram_id}, пользователь не существует")
            return False

        query = delete(Deadline).where(
            Deadline.user_id == user.id,
            Deadline.is_custom == True
        )
        await session.execute(query)
        await session.commit()
        logger.success(f'Все личные дедлайны удалены пользователю с telegram_id={telegram_id}')
        return True


async def get_trashed_deadlines_from_db(telegram_id: int) -> list[Deadline]:
    """Получает все дедлайны пользователя из корзины."""
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(telegram_id)
        if not user: return []
        query = (
            select(Deadline)
            .where(Deadline.user_id == user.id, Deadline.is_trashed == True)
            .order_by(Deadline.due_date.desc())
        )
        result = await session.execute(query)
        deadlines = result.scalars().all()
        logger.success(f'Пользователь с telegram_id={telegram_id} получил {len(deadlines)} дедлайнов из корзины')
        return list(deadlines)


async def restore_deadline_from_trash(deadline_id: int):
    """Восстанавливает дедлайн из корзины."""
    async with async_session_factory() as session:
        query = update(Deadline).where(Deadline.id == deadline_id).values(is_trashed=False)
        await session.execute(query)
        await session.commit()
        logger.success(f'Дедлайн с id={deadline_id} восстановлен из корзины')


async def empty_trash_for_user(telegram_id: int):
    """Перманентно удаляет все дедлайны из корзины пользователя."""
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(telegram_id)
        if not user: return False
        query = delete(Deadline).where(Deadline.user_id == user.id, Deadline.is_trashed == True)
        await session.execute(query)
        await session.commit()
        logger.success(f'Корзина очищена для пользователя с telegram_id={telegram_id}')
        return True


async def cleanup_expired_trashed_deadlines():
    """Автоматически удаляет просроченные дедлайны из корзин всех пользователей."""
    async with async_session_factory() as session:
        query = delete(Deadline).where(
            Deadline.is_trashed == True,
            Deadline.due_date < datetime.now().date()
        )
        result = await session.execute(query)
        await session.commit()
        logger.success(f"Очищено {result.rowcount} просроченных дедлайнов из корзин.")
