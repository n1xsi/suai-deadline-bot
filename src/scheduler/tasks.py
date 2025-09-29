import asyncio
from datetime import datetime

from aiogram import Bot
from loguru import logger

from src.database.queries import (
    get_all_users, get_user_by_telegram_id, get_user_deadlines_from_db, update_user_deadlines
)
from src.parser.scraper import parse_lk_data
from src.utils.crypto import decrypt_data


async def update_user_deadlines_and_notify(bot: Bot, user_id: int, force_notify: bool = False):
    """
    Задача для обновления дедлайнов пользователя.
    """
    logger.info(f"Запуск задачи обновления дедлайнов пользователя {user_id}...")

    user = await get_user_by_telegram_id(user_id)
    if not user:
        logger.warning(f"Не удалось обновить дедлайны для пользователя {user_id} (пользователь не существует)")
        return

    # Проверка, что у пользователя есть сохранённые учётные данные
    if not user.encrypted_login_lk or not user.encrypted_password_lk:
        logger.warning(f"Не удалось обновить дедлайны для пользователя {user.telegram_id} (нет сохранённых данных пользователя)")
        return

    # Расшифровка данных
    login = decrypt_data(user.encrypted_login_lk)
    password = decrypt_data(user.encrypted_password_lk)

    # Запуск парсера
    loop = asyncio.get_event_loop()
    parsed_data = await loop.run_in_executor(None, parse_lk_data, login, password)
    if parsed_data:
        deadlines_from_parser, _, _ = parsed_data
    else:
        logger.error(f"Не удалось обновить дедлайны для пользователя {user.telegram_id} (ошибка парсера)")
        return

    newly_added = await update_user_deadlines(user.telegram_id, deadlines_from_parser)

    if newly_added:
        # Если список не пустой, значит появились новые дедлайны
        logger.success(f"Найдено {len(newly_added)} новых дедлайнов для пользователя {user.telegram_id}")

        new_deadlines_text = "✨ <b>Обнаружены новые дедлайны!</b>\n\n"
        for d in newly_added:
            new_deadlines_text += (
                f"📚 <b>{d['course_name']}</b>\n"
                f"📝 {d['task_name']}\n"
                f"🗓️ Срок сдачи: {d['due_date'].strftime('%d.%m.%Y')}\n\n"
            )

        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=new_deadlines_text,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление о новых дедлайнах {user.telegram_id}. Ошибка: {e}")
    else:
        logger.info(f"Новых дедлайнов для пользователя {user.telegram_id} не найдено")
        if force_notify:
            await bot.send_message(
                chat_id=user.telegram_id,
                text="✅ Новых дедлайнов не найдено, всё по-прежнему!",
                parse_mode="HTML"
            )
    

async def update_all_deadlines(bot: Bot):
    """
    Задача для полного обновления дедлайнов и уведомления о новых.
    """
    logger.info("Запуск задачи обновления дедлайнов всех пользователей...")
    users = await get_all_users()
    for user in users:
        await update_user_deadlines_and_notify(bot, user.telegram_id)
        await asyncio.sleep(5)
    
    logger.success(f"Задача обновления дедлайнов для {len(users)} пользователей завершена")


async def send_deadline_notifications(bot: Bot):
    """
    Задача для отправки уведомлений о дедлайнах с учётом настроек пользователя.
    """
    logger.info("Запуск задачи отправки уведомлений о дедлайнах")
    current_hour = datetime.now().hour

    # Поиск только тех пользователей, кто хочет получать уведомления
    users_to_notify = await get_all_users(only_with_notifications=True)

    for user in users_to_notify:
        notification_sent_this_run = False
        user_deadlines = await get_user_deadlines_from_db(user.telegram_id)
        if not user_deadlines:
            continue

        # Логика для ежедневных уведомлений
        if user.notification_days and current_hour == 9:  # Отправка ежедневных в 9:00
            notification_days_set = set(map(int, user.notification_days.split(',')))
            today = datetime.now().date()
            for deadline in user_deadlines:
                days_left = (deadline.due_date.date() - today).days
                if days_left in notification_days_set:
                    text = (
                        f"🔔 <b>Напоминание о дедлайне!</b>\n\n"
                        f"📚 <b>Предмет:</b> {deadline.course_name}\n"
                        f"📝 <b>Задание:</b> {deadline.task_name}\n\n"
                        f"🗓️ <u>Осталось дней</u>: <b>{days_left}</b>"
                    )
                    try:
                        await bot.send_message(chat_id=user.telegram_id, text=text, parse_mode="HTML")
                        logger.success(f"Отправлено ЕЖЕДНЕВНОЕ уведомление пользователю {user.telegram_id}.")
                        notification_sent_this_run = True
                        break  # Отправка только одного ежедневного уведомления за раз
                    except Exception as e:
                        logger.error(f"Не удалось отправить уведомление {user.telegram_id}. Ошибка: {e}")

        # Логика для частых (часовых) уведомлений
        interval = user.notification_interval_hours
        if interval > 0 and current_hour % interval == 0 and not notification_sent_this_run:
            deadlines_text = "⏰ <b>Часовое напоминание!</b>\n\nВаши активные дедлайны:\n\n"
            for d in user_deadlines:
                deadlines_text += f"▪️ {d.course_name}: {d.task_name} (до {d.due_date.strftime('%d.%m')})\n"
            try:
                await bot.send_message(chat_id=user.telegram_id, text=deadlines_text, parse_mode="HTML")
                logger.success(f"Отправлено ЧАСТОЕ уведомление пользователю {user.telegram_id}")
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление {user.telegram_id}. Ошибка: {e}")

        await asyncio.sleep(1)
    logger.success("Задача отправки уведомлений завершена")
