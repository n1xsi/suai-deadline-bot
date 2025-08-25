from datetime import datetime

from aiogram import Bot
import asyncio

from src.database.queries import (
    get_all_users, get_user_deadlines_from_db, update_user_deadlines
)
from src.parser.scraper import parse_lk_data
from src.utils.crypto import decrypt_data


async def update_all_deadlines():
    """
    Задача для полного обновления дедлайнов для всех пользователей.
    """
    print("SCHEDULER: Запуск задачи обновления дедлайнов...")
    users = await get_all_users()
    for user in users:
        # Проверка, что у пользователя есть сохранённые учётные данные
        if not user.encrypted_login_lk or not user.encrypted_password_lk:
            continue

        # Расшифровка данных
        login = decrypt_data(user.encrypted_login_lk)
        password = decrypt_data(user.encrypted_password_lk)

        # Запуск парсера
        loop = asyncio.get_event_loop()
        deadlines = await loop.run_in_executor(None, parse_lk_data, login, password)

        if deadlines is not None:
            # Обновление дедлайнов в БД, если парсинг прошёл успешно
            await update_user_deadlines(user.telegram_id, deadlines)
            print(f"SCHEDULER: Дедлайны для пользователя {user.telegram_id} успешно обновлены.")
        else:
            print(f"SCHEDULER: Не удалось обновить дедлайны для {user.telegram_id} (ошибка парсера).")

        # Небольшая задержка, чтобы не перегружать сайт ЛК
        await asyncio.sleep(5)

    print("SCHEDULER: Задача обновления дедлайнов завершена.")


async def send_deadline_notifications(bot: Bot):
    """
    Задача для отправки уведомлений о дедлайнах с учётом настроек пользователя.
    """
    print("SCHEDULER: Запуск задачи отправки уведомлений...")
    current_hour = datetime.now().hour

    # Поиск только тех пользователей, кто хочет получать уведомления
    users_to_notify = await get_all_users(only_with_notifications=True)

    for user in users_to_notify:
        notification_sent_this_run = False
        user_deadlines = await get_user_deadlines_from_db(user.telegram_id)
        if not user_deadlines:
            continue

        # Логика для ЕЖЕДНЕВНЫХ уведомлений
        if user.notification_days and current_hour == 9: # Отправляем ежедневные в 9:00
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
                        print(f"SCHEDULER: Отправлено ЕЖЕДНЕВНОЕ уведомление пользователю {user.telegram_id}.")
                        notification_sent_this_run = True
                        break # Отправляем только одно ежедневное уведомление за раз
                    except Exception as e:
                        print(f"SCHEDULER: Не удалось отправить уведомление {user.telegram_id}. Ошибка: {e}")

        # Логика для ЧАСТЫХ (часовых) уведомлений
        interval = user.notification_interval_hours
        if interval > 0 and current_hour % interval == 0 and not notification_sent_this_run:
            deadlines_text = "⏰ <b>Часовое напоминание!</b>\n\nВаши активные дедлайны:\n\n"
            for d in user_deadlines:
                deadlines_text += f"▪️ {d.course_name}: {d.task_name} (до {d.due_date.strftime('%d.%m')})\n"
            try:
                await bot.send_message(chat_id=user.telegram_id, text=deadlines_text, parse_mode="HTML")
                print(f"SCHEDULER: Отправлено ЧАСТОЕ уведомление пользователю {user.telegram_id}.")
            except Exception as e:
                print(f"SCHEDULER: Не удалось отправить уведомление {user.telegram_id}. Ошибка: {e}")
        
        await asyncio.sleep(1)
    print("SCHEDULER: Задача отправки уведомлений завершена.")
