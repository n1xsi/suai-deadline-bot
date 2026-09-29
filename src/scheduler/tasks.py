from src.database.queries import (
    get_all_users, get_user_by_telegram_id, get_user_deadlines_from_db,
    update_user_deadlines, cleanup_expired_trashed_deadlines, count_undated_deadlines
)
from src.parser.scraper import parse_lk_data
from src.utils.crypto import decrypt_data

from src.utils.formatting import task_link, NO_LINK_PREVIEW

from cryptography.fernet import InvalidToken
from datetime import datetime
from html import escape

from loguru import logger
from aiogram import Bot
import asyncio


async def update_user_deadlines_and_notify(bot: Bot, user_id: int, force_notify: bool = False):
    """
    Задача для обновления дедлайнов пользователя

    :param bot: Бот для отправки уведомлений
    :param user_id: ID пользователя
    :param force_notify: Флаг, указывающий, будет ли отправляться уведомление если дедлайны не обновились
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
    try:
        login = decrypt_data(user.encrypted_login_lk)
        password = decrypt_data(user.encrypted_password_lk)
    except InvalidToken:
        logger.error(
            f"Не удалось расшифровать учётные данные пользователя {user.telegram_id}: "
            f"возможно текущий ENCRYPTION_KEY не соответствует ключу, которым данные были зашифрованы"
        )
        if force_notify:
            await bot.send_message(
                chat_id=user.telegram_id,
                text="⛔ Не удалось прочитать ваши сохранённые данные от личного кабинета — "
                     "возникла проблема с ключом шифрования.\n\n"
                     "🔑 Пожалуйста, пройдите регистрацию заново: команда /stop (удалит ваши данные), "
                     "а затем /start."
            )
        return

    # Запуск парсера
    loop = asyncio.get_event_loop()
    parsed_data = await loop.run_in_executor(None, parse_lk_data, login, password)
    if parsed_data:
        deadlines_from_parser, _, _ = parsed_data
    else:
        logger.error(f"Не удалось обновить дедлайны для пользователя {user.telegram_id} (ошибка парсера)")
        return

    sync_result = await update_user_deadlines(user.telegram_id, deadlines_from_parser)

    new_dated = sync_result['new_dated']
    new_undated = sync_result['new_undated']
    got_lk_date = sync_result['got_lk_date']

    message_blocks = []

    if new_dated:
        block = "✨ <b>Обнаружены новые дедлайны!</b>\n\n"
        for d in new_dated:
            block += (
                f"📚 <b>{escape(d['course_name'])}</b>\n"
                f"📝 {task_link(d['task_name'], d.get('task_url'))}\n"
                f"🗓️ Срок сдачи: {d['due_date'].strftime('%d.%m.%Y')}\n\n"
            )
        message_blocks.append(block.rstrip())

    if new_undated:
        block = "❔ <b>Новые задания без указанного срока сдачи</b>\n\n"
        for d in new_undated:
            block += (
                f"📚 <b>{escape(d['course_name'])}</b>\n"
                f"📝 {task_link(d['task_name'], d.get('task_url'))}\n\n"
            )
        block += (
            "<i>Назначить свой срок: «🚨 Посмотреть дедлайны» → «❔ Без срока сдачи».</i>"
        )
        message_blocks.append(block)

    if got_lk_date:
        block = "🗓️ <b>В ЛК появился официальный срок сдачи</b>\n\n"
        for d in got_lk_date:
            block += (
                f"📚 <b>{escape(d['course_name'])}</b>\n"
                f"📝 {task_link(d['task_name'], d.get('task_url'))}\n"
            )
            # Дата из ЛК считается источником истины и заменяет выставленную пользователем
            if d['previous_user_date']:
                block += (
                    f"🔄 Ваш срок {d['previous_user_date'].strftime('%d.%m.%Y')} заменён на "
                    f"<b>{d['due_date'].strftime('%d.%m.%Y')}</b>\n\n"
                )
            else:
                block += f"🗓️ Срок сдачи: <b>{d['due_date'].strftime('%d.%m.%Y')}</b>\n\n"
        message_blocks.append(block.rstrip())

    if message_blocks:
        logger.success(
            f"Для пользователя {user.telegram_id} найдено: {len(new_dated)} новых дедлайнов, "
            f"{len(new_undated)} без срока сдачи, {len(got_lk_date)} с появившейся датой из ЛК"
        )
        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text="\n\n".join(message_blocks),
                parse_mode="HTML",
                link_preview_options=NO_LINK_PREVIEW
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
        # Сбой у одного пользователя (недоступный ЛК, битые учётные данные) не должен прерывать обновление для всех остальных
        try:
            await update_user_deadlines_and_notify(bot, user.telegram_id)
        except Exception as e:
            logger.exception(f"Ошибка при обновлении дедлайнов пользователя {user.telegram_id}: {e}")
        await asyncio.sleep(5)
    
    logger.success(f"Задача обновления дедлайнов для {len(users)} пользователей завершена")


def _undated_hint(undated_count: int) -> str:
    """Приписка к напоминанию о том, что есть задания без указанного срока сдачи."""
    if not undated_count:
        return ""
    return f"\n\n❔ Ещё <b>{undated_count}</b> заданий без указанного срока сдачи — можно назначить свой."


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
        undated_count = await count_undated_deadlines(user.telegram_id)

        # Пропуск пользователя, только если напоминать вообще не о чем
        if not user_deadlines and not undated_count:
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
                        f"📚 <b>Предмет:</b> {escape(deadline.course_name)}\n"
                        f"📝 <b>Задание:</b> {task_link(deadline.task_name, deadline.task_url)}\n\n"
                        f"🗓️ <u>Осталось дней</u>: <b>{days_left}</b>"
                        f"{_undated_hint(undated_count)}"
                    )
                    try:
                        await bot.send_message(
                            chat_id=user.telegram_id,
                            text=text,
                            parse_mode="HTML",
                            link_preview_options=NO_LINK_PREVIEW
                        )
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
                deadlines_text += (
                    f"▪️ {escape(d.course_name)}: {task_link(d.task_name, d.task_url)} "
                    f"(до {d.due_date.strftime('%d.%m')})\n"
                )
            if not user_deadlines:
                deadlines_text += "<i>нет дедлайнов с указанным сроком</i>\n"
            deadlines_text += _undated_hint(undated_count)
            try:
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=deadlines_text,
                    parse_mode="HTML",
                    link_preview_options=NO_LINK_PREVIEW
                )
                logger.success(f"Отправлено ЧАСТОЕ уведомление пользователю {user.telegram_id}")
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление {user.telegram_id}. Ошибка: {e}")

        await asyncio.sleep(1)
    logger.success("Задача отправки уведомлений завершена")


async def cleanup_expired_trashed_deadlines_task():
    """Задача для автоматической очистки просроченных дедлайнов из корзин."""
    logger.info("Запуск задачи очистки просроченных дедлайнов из корзин...")
    await cleanup_expired_trashed_deadlines()
    logger.success("Задача очистки просроченных дедлайнов завершена.")
