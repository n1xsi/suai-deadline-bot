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
    builder.adjust(1)  # Расположение кнопок по одной в строке
    return builder.as_markup()


def get_confirm_keyboard(
    confirm_text: str,
    confirm_callback: str,
    cancel_text: str,
    cancel_callback: str
):
    """
    Создаёт универсальную клавиатуру для подтверждения действий.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text=f"✅ {confirm_text}", callback_data=confirm_callback)
    builder.button(text=f"❌ {cancel_text}", callback_data=cancel_callback)
    builder.adjust(2)
    return builder.as_markup()


def get_cancel_keyboard():
    buttons = [[KeyboardButton(text="❌ Отмена")]]
    keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    return keyboard


def get_deadlines_settings_keyboard(deadlines: list, current_page: int, page_size: int, user_id: int):
    """
    Создаёт пагинированную клавиатуру для удаления дедлайнов.
    Каждый дедлайн - это кнопка для его удаления.
    """
    builder = InlineKeyboardBuilder()

    total_pages = (len(deadlines) + page_size - 1) // page_size

    # "Нарезка" списка дедлайнов для текущей страницы
    start_index = current_page * page_size
    end_index = start_index + page_size
    page_deadlines = deadlines[start_index:end_index]

    # Создание кнопок для удаления дедлайнов
    for deadline in page_deadlines:
        builder.button(
            text=f"❌ {deadline.course_name[:20]}... ({deadline.due_date.strftime('%d.%m')})",
            callback_data=f"del_deadline_{deadline.id}"
        )

    # Дополнительные кнопки действий в отдельных рядах
    builder.row(InlineKeyboardButton(text="➕ Добавить собственный дедлайн", callback_data="add_deadline"))
    builder.row(InlineKeyboardButton(text="📨 Синхронизировать дедлайны с ЛК", callback_data=f"update_{user_id}"))

    pagination_buttons = []
    if current_page > 0:
        pagination_buttons.append(
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"settings_page_{current_page - 1}")
        )
    if total_pages > 1:
        pagination_buttons.append(
            InlineKeyboardButton(text=f"📄 {current_page + 1}/{total_pages}", callback_data="ignore")
        )
    if current_page < total_pages - 1:
        pagination_buttons.append(
            InlineKeyboardButton(text="Вперед ➡️", callback_data=f"settings_page_{current_page + 1}")
        )

    # Если кнопок пагинации больше нуля, то они добавляются в ряд
    if pagination_buttons:
        builder.row(*pagination_buttons)

    # Выстраивание кнопок: по одной на дедлайн, затем действия и ряд пагинации
    builder.adjust(*([1] * len(page_deadlines)), 1, 1, len(pagination_buttons))
    return builder.as_markup()


def get_notification_settings_keyboard(user: User):
    """Создаёт клавиатуру настроек уведомлений на основе данных пользователя."""
    builder = InlineKeyboardBuilder()

    # Кнопка включения/выключения
    status_text = "✅ Вкл." if user.notifications_enabled else "❌ Выкл."
    builder.button(text=f"Напоминания: {status_text}", callback_data="toggle_notifications")

    # Кнопка для настройки частоты уведомлений по часам
    interval = user.notification_interval_hours
    interval_text = f"✅ {interval} ч." if interval > 0 else "❌ Выкл."
    builder.button(text=f"Частые: {interval_text}", callback_data="set_interval")

    # Кнопки для дней уведомлений
    user_days = set(map(int, user.notification_days.split(','))) if user.notification_days else set()
    possible_days = [1, 3, 7]

    day_buttons = []
    for day in possible_days:
        text = f"✅ за {day} д." if day in user_days else f"🔕 за {day} д."
        day_buttons.append(InlineKeyboardButton(text=text, callback_data=f"toggle_day_{day}"))

    # Ряд с кнопками дней
    builder.row(*day_buttons)
    return builder.as_markup()


def get_pagination_keyboard(current_page: int, total_pages: int):
    """
    Создаёт клавиатуру для пагинации (Вперёд/Назад).
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


def get_update_button(user_id: int):
    """
    Создаёт кнопку для обновления дедлайнов.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="Обновить", callback_data=f"update_{user_id}")
    return builder.as_markup()
