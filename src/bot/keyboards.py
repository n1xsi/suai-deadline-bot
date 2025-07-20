from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_main_menu_keyboard():
    """Создает клавиатуру главного меню."""
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

def get_profile_keyboard():
    """Создает inline-клавиатуру для меню 'Мой профиль'."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑️ Удалить все мои данные", callback_data="delete_my_data")
    return builder.as_markup()

def get_confirm_delete_keyboard():
    """Создает inline-клавиатуру для подтверждения удаления."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data="confirm_delete")
    builder.button(text="❌ Нет, оставить", callback_data="cancel_delete")
    builder.adjust(2) # Расположение кнопок в один ряд по две 
    return builder.as_markup()

def get_cancel_keyboard():
    buttons = [[KeyboardButton(text="❌ Отмена")]]
    keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    return keyboard


def get_deadlines_settings_keyboard(deadlines: list):
    """
    Создает клавиатуру для управления дедлайнами.
    Каждый дедлайн - это кнопка для его удаления.
    """
    builder = InlineKeyboardBuilder()
    if deadlines:
        for deadline in deadlines:
            # В callback_data передаем префикс "del_deadline_" и id дедлайна
            builder.button(
                text=f"❌ {deadline.course_name[:20]}... ({deadline.due_date.strftime('%d.%m')})",
                callback_data=f"del_deadline_{deadline.id}"
            )
    
    # Кнопка для добавления нового дедлайна
    builder.button(text="➕ Добавить дедлайн вручную", callback_data="add_deadline")
    # Кнопка для возврата в главное меню
    builder.button(text="⬅️ Назад в меню", callback_data="back_to_main")
    
    # Выстраиваем кнопки: по одной на дедлайн, и две последних в ряд
    builder.adjust(*([1] * len(deadlines)), 1, 1)
    return builder.as_markup()