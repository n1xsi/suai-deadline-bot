from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.database.models import User


def get_main_menu_keyboard():
    """Создаёт клавиатуру главного меню."""
    buttons = [
        [KeyboardButton(text="🚨 Посмотреть дедлайны")],
        [
            KeyboardButton(text="🔔 Настройка напоминаний"),
            KeyboardButton(text="👤 Мой профиль"),
            KeyboardButton(text="🛠️ Настройка дедлайнов")
        ]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    return keyboard


def get_profile_keyboard(custom_deadlines_count: int = 0):
    """
    Создаёт inline-клавиатуру для меню 'Мой профиль'.
    Динамически добавляет кнопку удаления личных дедлайнов.
    """
    builder = InlineKeyboardBuilder()
    
    if custom_deadlines_count > 0:
        builder.button(
            text=f"🚮 Удалить все личные дедлайны", 
            callback_data="delete_all_custom"
        )
    
    builder.button(text="🗑️ Удалить все мои данные", callback_data="delete_my_data")
    
    # Расположение кнопок по одной в строке
    builder.adjust(1)
    return builder.as_markup()


def get_confirm_delete_keyboard():
    """Создаёт inline-клавиатуру для подтверждения удаления."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data="confirm_delete")
    builder.button(text="❌ Нет, оставить", callback_data="cancel_delete")
    builder.adjust(2)  # Расположение кнопок в один ряд по две
    return builder.as_markup()


def get_cancel_keyboard():
    buttons = [[KeyboardButton(text="❌ Отмена")]]
    keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    return keyboard


def get_deadlines_settings_keyboard(deadlines: list):
    """
    Создаёт клавиатуру для управления дедлайнами.
    Каждый дедлайн - это кнопка для его удаления.
    """
    builder = InlineKeyboardBuilder()
    if deadlines:
        for deadline in deadlines:
            builder.button(
                text=f"❌ {deadline.course_name[:20]}... ({deadline.due_date.strftime('%d.%m')})",
                callback_data=f"del_deadline_{deadline.id}"
            )

    builder.button(text="➕ Добавить собственный дедлайн", callback_data="add_deadline")
    builder.button(text="⬅️ Назад", callback_data="back_to_main_from_settings")

    # Выстраиваем кнопки: по одной на дедлайн, и две последних в ряд
    builder.adjust(*([1] * len(deadlines)), 1, 1)
    return builder.as_markup()


def get_notification_settings_keyboard(user: User):
    """Создаёт клавиатуру настроек уведомлений на основе данных пользователя."""
    builder = InlineKeyboardBuilder()

    # Кнопка включения/выключения
    status_text = "✅ Включены" if user.notifications_enabled else "❌ Выключены"
    builder.button(text=f"Напоминания: {status_text}", callback_data="toggle_notifications")
    
    # Кнопка для настройки частоты уведомлений по часам
    interval = user.notification_interval_hours
    interval_text = f"{interval} ч." if interval > 0 else "Выкл."
    builder.button(text=f"Частые уведомления: {interval_text}", callback_data="set_interval")

    # Кнопки для дней уведомлений
    user_days = set(map(int, user.notification_days.split(','))) if user.notification_days else set()
    possible_days = [1, 3, 7]

    day_buttons = []
    for day in possible_days:
        text = f"✅ за {day} д." if day in user_days else f"🔕 за {day} д."
        day_buttons.append(InlineKeyboardButton(
            text=text, callback_data=f"toggle_day_{day}"))

    # Ряд с кнопками дней
    builder.row(*day_buttons)

    # Кнопка для возврата в главное меню
    builder.button(text="⬅️ Назад", callback_data="back_to_main_from_settings")
    return builder.as_markup()


def get_confirm_delete_deadline_keyboard(deadline_id: int):
    """Создаёт inline-клавиатуру для подтверждения удаления дедлайна."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data=f"confirm_del_deadline_{deadline_id}")
    builder.button(text="❌ Нет, оставить", callback_data="cancel_del_deadline")
    builder.adjust(2)
    return builder.as_markup()


def get_confirm_delete_all_custom_keyboard():
    """Создаёт inline-клавиатуру для подтверждения удаления ВСЕХ личных дедлайнов."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить все", callback_data="confirm_delete_all_custom")
    builder.button(text="❌ Нет, отмена", callback_data="cancel_delete_all_custom")
    builder.adjust(2)
    return builder.as_markup()


def get_pagination_keyboard(current_page: int, total_pages: int):
    """
    Создает клавиатуру для пагинации (Вперёд/Назад).
    """
    builder = InlineKeyboardBuilder()
    
    # Кнопка "Назад" не показывается, если это первая страница
    if current_page > 0:
        builder.button(text="⬅️ Назад", callback_data=f"page_{current_page - 1}")
        
    # Индикатор страницы ('ignore' - чтобы нажатие на кнопку не делало ничего)
    builder.button(text=f"📄 {current_page + 1} / {total_pages}", callback_data="ignore")
    
    # Кнопка "Вперёд" не показывается, если это последняя страница
    if current_page < total_pages - 1:
        builder.button(text="Вперёд ➡️", callback_data=f"page_{current_page + 1}")
        
    # Расположение кнопок в один ряд
    builder.adjust(3)
    return builder.as_markup()
