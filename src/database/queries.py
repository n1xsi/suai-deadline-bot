from datetime import datetime, timedelta
from typing import Optional, List, Dict

from loguru import logger
from sqlalchemy import select, update, delete, func, or_

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


async def update_user_deadlines(telegram_id: int, new_parsed_deadlines: list[dict]) -> Dict[str, List[Dict]]:
    """
    "Умно" синхронизирует дедлайны из парсера с базой данных:
    1) Не трогает личные дедлайны (добавленные вручную)
    2) Не добавляет дедлайны, которые занесены в корзину
    3) Обновляет дату, если срок сдачи дедлайна изменился
    4) Сохраняет дедлайны без указанного в ЛК срока сдачи (due_date = None)
    5) Не затирает срок, выставленный пользователем, пока в ЛК нет официальной даты

    Возвращает словарь с тремя списками:
      'new_dated'   - новые дедлайны с указанным сроком сдачи
      'new_undated' - новые дедлайны без срока сдачи
      'got_lk_date' - дедлайны, у которых в ЛК появилась официальная дата
                      (ключ 'previous_user_date' - дата, ранее выставленная пользователем, или None)
    """
    new_dated: List[Dict] = []
    new_undated: List[Dict] = []
    got_lk_date: List[Dict] = []

    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            return {'new_dated': new_dated, 'new_undated': new_undated, 'got_lk_date': got_lk_date}

        # Получение ВСЕХ парсерных дедлайнов (и активных, и из корзины)
        existing_deadlines_query = await session.execute(
            select(Deadline).where(Deadline.user_id == user.id, Deadline.is_custom == False)
        )
        existing_deadlines_list = existing_deadlines_query.scalars().all()

        # Создание множества для быстрой проверки (ключ: предмет + задание)
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
        objects_to_add_in_db = []

        for key, data in parsed_deadlines_set.items():
            raw_due_date = data.get('due_date')
            task_url = data.get('url')

            # due_date = None означает, что в ЛК у задания не указана предельная дата
            if raw_due_date:
                try:
                    due_date_obj = datetime.strptime(raw_due_date, "%d.%m.%Y")
                except ValueError:
                    logger.warning(f"Не удалось разобрать дату '{raw_due_date}' для задания '{data['task']}'")
                    due_date_obj = None
            else:
                due_date_obj = None

            # Новый дедлайн, которого нет в БД
            if key not in existing_deadlines_set:
                deadline_data = {
                    'course_name': data['subject'],
                    'task_name': data['task'],
                    'due_date': due_date_obj,
                    'task_url': task_url
                }

                if due_date_obj:
                    new_dated.append(deadline_data)
                else:
                    new_undated.append(deadline_data)

                objects_to_add_in_db.append(
                    Deadline(
                        user_id=user.id,
                        course_name=data['subject'],
                        task_name=data['task'],
                        due_date=due_date_obj,
                        task_url=task_url,
                        is_custom=False
                    )
                )

            # Дедлайн уже есть в БД
            else:
                existing_dl = existing_deadlines_set[key]

                # Дозапись ссылки на задание (бэкфилл записей, созданных до появления поля)
                if task_url and existing_dl.task_url != task_url:
                    existing_dl.task_url = task_url

                # В ЛК срока сдачи нет: не затираем ни NULL, ни дату, выставленную пользователем
                if due_date_obj is None:
                    continue

                # Проверка, изменилась ли дата сдачи на сайте
                if existing_dl.due_date is None or existing_dl.due_date.date() != due_date_obj.date():
                    # Дата из ЛК считается источником истины и перезаписывает пользовательскую
                    if existing_dl.due_date is None or existing_dl.is_user_dated:
                        got_lk_date.append({
                            'course_name': existing_dl.course_name,
                            'task_name': existing_dl.task_name,
                            'due_date': due_date_obj,
                            'task_url': task_url or existing_dl.task_url,
                            'previous_user_date': existing_dl.due_date if existing_dl.is_user_dated else None
                        })

                    existing_dl.due_date = due_date_obj
                    existing_dl.is_user_dated = False


        if objects_to_add_in_db:
            session.add_all(objects_to_add_in_db)

        await session.commit()
        if objects_to_add_in_db:
            logger.success(
                f'Добавлено {len(objects_to_add_in_db)} дедлайнов '
                f'({len(new_undated)} из них без срока сдачи)'
            )

        return {'new_dated': new_dated, 'new_undated': new_undated, 'got_lk_date': got_lk_date}


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

        # Подсчёт всех активных дедлайнов
        all_active_query = select(func.count(Deadline.id)).where(
            Deadline.user_id == user.id,
            Deadline.due_date >= datetime.now().date(),
            Deadline.is_trashed == False
        )
        all_active_count = await session.execute(all_active_query)

        # Подсчёт личных дедлайнов
        custom_active_query = select(func.count(Deadline.id)).where(
            Deadline.user_id == user.id,
            Deadline.due_date >= datetime.now().date(),
            Deadline.is_custom == True,
            Deadline.is_trashed == False
        )
        custom_active_count = await session.execute(custom_active_query)

        # Подсчёт дедлайнов без указанного в ЛК срока сдачи
        undated_query = select(func.count(Deadline.id)).where(
            Deadline.user_id == user.id,
            Deadline.due_date.is_(None),
            Deadline.is_trashed == False
        )
        undated_count_result = await session.execute(undated_query)

        # Подсчёт дедлайнов в корзине
        trashed_query = select(func.count(Deadline.id)).where(
            Deadline.user_id == user.id,
            Deadline.is_trashed == True
        )
        trashed_active_count = await session.execute(trashed_query)

        active_count = all_active_count.scalar_one_or_none() or 0
        custom_count = custom_active_count.scalar_one_or_none() or 0
        undated_count = undated_count_result.scalar_one_or_none() or 0
        trashed_count = trashed_active_count.scalar_one_or_none() or 0

        logger.success(
            f'Статистика пользователя {telegram_id}: {active_count} активных дедлайнов, '
            f'{custom_count} личных, {undated_count} без срока сдачи, {trashed_count} в корзине'
        )

        return {
            "active_deadlines": active_count,
            "custom_deadlines": custom_count,
            "undated_deadlines": undated_count,
            "trashed_deadlines": trashed_count
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
    """
    Получает все актуальные дедлайны пользователя из БД.
    Дедлайны без указанного срока сдачи сюда НЕ попадают - для них есть
    get_undated_deadlines_from_db().
    """
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
                Deadline.due_date.is_not(None),
                Deadline.due_date >= datetime.now().date(),
                Deadline.is_trashed == False
                )
            .order_by(Deadline.due_date.asc())
        )
        result = await session.execute(query)
        deadlines = result.scalars().all()
        logger.success(f'Пользователь с telegram_id={telegram_id} имеет {len(deadlines)} дедлайнов')
        return list(deadlines)


async def get_undated_deadlines_from_db(telegram_id: int) -> list[Deadline]:
    """Получает дедлайны пользователя, у которых в ЛК не указан срок сдачи."""
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            logger.error(
                f'Не удалось получить дедлайны без срока сдачи для telegram_id={telegram_id}, '
                f'пользователя не существует'
            )
            return []

        query = (
            select(Deadline)
            .where(
                Deadline.user_id == user.id,
                Deadline.due_date.is_(None),
                Deadline.is_trashed == False
            )
            .order_by(Deadline.course_name.asc(), Deadline.task_name.asc())
        )
        result = await session.execute(query)
        deadlines = result.scalars().all()
        logger.success(f'Пользователь с telegram_id={telegram_id} имеет {len(deadlines)} дедлайнов без срока сдачи')
        return list(deadlines)


async def get_manageable_deadlines_from_db(telegram_id: int) -> list[Deadline]:
    """
    Получает все дедлайны, которыми пользователь может управлять в меню настроек:
    актуальные (с не прошедшим сроком) и те, у которых срок сдачи не указан.
    Сначала идут дедлайны с датой (по возрастанию срока), затем бездатные.
    """
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            logger.error(
                f'Не удалось получить управляемые дедлайны для telegram_id={telegram_id}, '
                f'пользователя не существует'
            )
            return []

        query = (
            select(Deadline)
            .where(
                Deadline.user_id == user.id,
                Deadline.is_trashed == False,
                or_(
                    Deadline.due_date.is_(None),
                    Deadline.due_date >= datetime.now().date()
                )
            )
            # is_(None) даёт 0 для дат и 1 для NULL - бездатные оказываются в конце списка
            .order_by(Deadline.due_date.is_(None), Deadline.due_date.asc())
        )
        result = await session.execute(query)
        deadlines = result.scalars().all()
        logger.success(f'Пользователь с telegram_id={telegram_id} имеет {len(deadlines)} управляемых дедлайнов')
        return list(deadlines)


async def count_undated_deadlines(telegram_id: int) -> int:
    """Считает дедлайны пользователя без указанного срока сдачи (для счётчика на кнопке)."""
    async with async_session_factory() as session:
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            return 0

        query = select(func.count(Deadline.id)).where(
            Deadline.user_id == user.id,
            Deadline.due_date.is_(None),
            Deadline.is_trashed == False
        )
        result = await session.execute(query)
        return result.scalar_one_or_none() or 0


async def set_deadline_due_date(deadline_id: int, due_date: datetime) -> bool:
    """
    Назначает дедлайну срок сдачи, выставленный самим пользователем.

    Обновление срабатывает только если у дедлайна срока ещё нет: пока пользователь набирал
    дату, синхронизация могла подтянуть официальную дату из ЛК - её перезаписывать нельзя.
    Возвращает True, если дата была назначена.
    """
    async with async_session_factory() as session:
        query = (
            update(Deadline)
            .where(Deadline.id == deadline_id, Deadline.due_date.is_(None))
            .values(due_date=due_date, is_user_dated=True)
        )
        result = await session.execute(query)
        await session.commit()

        if result.rowcount:
            logger.success(f'Дедлайну с id={deadline_id} назначен срок сдачи {due_date.strftime("%d.%m.%Y")}')
            return True

        logger.warning(f'Не удалось назначить срок сдачи дедлайну с id={deadline_id} (срок уже есть или дедлайн удалён)')
        return False


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
    """
    Автоматически удаляет просроченные дедлайны из корзин всех пользователей.
    Дедлайны без срока сдачи не трогаются: у них нечему истекать.
    """
    async with async_session_factory() as session:
        query = delete(Deadline).where(
            Deadline.is_trashed == True,
            Deadline.due_date.is_not(None),
            Deadline.due_date < datetime.now().date()
        )
        result = await session.execute(query)
        await session.commit()
        logger.success(f"Очищено {result.rowcount} просроченных дедлайнов из корзин.")
