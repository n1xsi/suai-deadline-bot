from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.database.models import User, Deadline


def _short_date(deadline: Deadline) -> str:
    """Короткая подпись срока сдачи для текста кнопки (у дедлайна его может не быть)."""
    return deadline.due_date.strftime('%d.%m') if deadline.due_date else "без срока"


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

    builder.button(text="📛 Удалить все мои данные", callback_data="delete_my_data")
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
            text=f"❌ {deadline.course_name[:20]}... ({_short_date(deadline)})",
            callback_data=f"del_deadline_{deadline.id}"
        )

    # Дополнительные кнопки действий в отдельных рядах
    builder.row(InlineKeyboardButton(text="➕ Добавить собственный дедлайн", callback_data="add_deadline"))
    builder.row(InlineKeyboardButton(text="📨 Синхронизировать дедлайны с ЛК", callback_data=f"update_{user_id}"))
    builder.row(InlineKeyboardButton(text="🗑️ Корзина", callback_data="open_trash_bin"))

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

    # Формирование схемы расположения кнопок:
    # По одной кнопке на каждый дедлайн
    sizes = [1] * len(page_deadlines)

    # Три статические кнопки, каждая в своем ряду (Добавить, Обновить, Корзина)
    sizes.extend([1, 1, 1])

    # Если есть пагинация - добавление её размера (кол-во кнопок в ряду пагинации)
    if pagination_buttons:
        sizes.append(len(pagination_buttons))

    builder.adjust(*sizes)
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


def get_undated_button(undated_count: int) -> InlineKeyboardButton:
    """Кнопка-вход на страницу дедлайнов без указанного срока сдачи."""
    return InlineKeyboardButton(
        text=f"❔ Без срока сдачи ({undated_count})",
        callback_data="undated_page_0"
    )


def get_pagination_keyboard(current_page: int, total_pages: int, undated_count: int = 0):
    """
    Создаёт клавиатуру для пагинации (Вперёд/Назад).
    Если есть дедлайны без указанного срока сдачи - внизу добавляется кнопка-вход на их страницу.
    """
    builder = InlineKeyboardBuilder()

    nav_buttons = []

    # Кнопка "Назад" не показывается, если это первая страница
    if current_page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"page_{current_page - 1}")
        )

    # Индикатор страницы ('ignore' - чтобы нажатие на кнопку не делало ничего)
    nav_buttons.append(
        InlineKeyboardButton(text=f"📄 {current_page + 1} / {total_pages}", callback_data="ignore")
    )

    # Кнопка "Вперёд" не показывается, если это последняя страница
    if current_page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"page_{current_page + 1}")
        )

    # Ряды добавляются явно: builder.adjust() переформатировал бы все кнопки сразу
    builder.row(*nav_buttons)

    if undated_count > 0:
        builder.row(get_undated_button(undated_count))

    return builder.as_markup()


def get_undated_deadlines_keyboard(deadlines: list, current_page: int, page_size: int):
    """
    Создаёт пагинированную клавиатуру для страницы дедлайнов без срока сдачи.
    На каждый дедлайн - ряд из двух кнопок: назначить срок и убрать в корзину.
    Номера кнопок совпадают с нумерацией дедлайнов в тексте сообщения.
    """
    builder = InlineKeyboardBuilder()

    total_pages = (len(deadlines) + page_size - 1) // page_size

    start_index = current_page * page_size
    end_index = start_index + page_size
    page_deadlines = deadlines[start_index:end_index]

    for number, deadline in enumerate(page_deadlines, start=start_index + 1):
        builder.row(
            InlineKeyboardButton(
                text=f"🗓️ {number}. {deadline.course_name[:18]}...",
                callback_data=f"setdate_{deadline.id}_{current_page}"
            ),
            InlineKeyboardButton(
                text=f"🗑️ {number}",
                callback_data=f"undated_trash_{deadline.id}_{current_page}"
            )
        )

    pagination_buttons = []
    if current_page > 0:
        pagination_buttons.append(
            InlineKeyboardButton(text="⬅️", callback_data=f"undated_page_{current_page - 1}")
        )
    if total_pages > 1:
        pagination_buttons.append(
            InlineKeyboardButton(text=f"📄 {current_page + 1}/{total_pages}", callback_data="ignore")
        )
    if current_page < total_pages - 1:
        pagination_buttons.append(
            InlineKeyboardButton(text="➡️", callback_data=f"undated_page_{current_page + 1}")
        )

    if pagination_buttons:
        builder.row(*pagination_buttons)

    builder.row(InlineKeyboardButton(text="⬅️ К списку дедлайнов", callback_data="page_0"))
    return builder.as_markup()


def get_cancel_setdate_keyboard():
    """Inline-кнопка отмены ввода собственного срока сдачи."""
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="cancel_setdate")
    return builder.as_markup()


def get_back_to_deadlines_keyboard():
    """Кнопка возврата к основному списку дедлайнов (со страницы без срока сдачи)."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ К списку дедлайнов", callback_data="page_0")
    return builder.as_markup()


def get_update_button(user_id: int, undated_count: int = 0):
    """
    Создаёт кнопку для обновления дедлайнов.
    Если есть дедлайны без срока сдачи - рядом появляется кнопка-вход на их страницу,
    иначе она была бы недостижима при пустом списке актуальных дедлайнов.
    """
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔄 Обновить", callback_data=f"update_{user_id}"))

    if undated_count > 0:
        builder.row(get_undated_button(undated_count))

    return builder.as_markup()


def get_trash_bin_keyboard(deadlines: list, current_page: int, page_size: int):
    """Создаёт пагинированную клавиатуру для корзины."""
    builder = InlineKeyboardBuilder()
    total_pages = (len(deadlines) + page_size - 1) // page_size

    start_index = current_page * page_size
    end_index = start_index + page_size
    page_deadlines = deadlines[start_index:end_index]

    # Кнопки для восстановления
    for deadline in page_deadlines:
        builder.button(
            text=f"♻️ {deadline.course_name[:20]}... ({_short_date(deadline)})",
            callback_data=f"restore_{deadline.id}"
        )

    pagination_buttons = []
    if current_page > 0:
        pagination_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"trash_page_{current_page - 1}"))
    if total_pages > 1:
        pagination_buttons.append(InlineKeyboardButton(text=f"📄 {current_page + 1}/{total_pages}", callback_data="ignore"))
    if current_page < total_pages - 1:
        pagination_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"trash_page_{current_page + 1}"))
    
    if pagination_buttons:
        builder.row(*pagination_buttons)

    # Кнопки действий
    if deadlines: # Показ кнопки "Очистить", только если корзина не пуста
         builder.row(InlineKeyboardButton(text="💥 Очистить корзину 💥", callback_data="empty_trash"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад в настройки", callback_data="back_to_settings"))

    builder.adjust(*([1] * len(page_deadlines)))
    return builder.as_markup()
