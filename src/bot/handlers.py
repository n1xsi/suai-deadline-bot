from datetime import datetime

from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from typing import Union

from src.database.queries import (
    add_user, set_user_credentials, update_user_deadlines, add_custom_deadline,
    delete_deadline_by_id, toggle_notifications, update_notification_days,
    get_user_by_telegram_id, get_user_deadlines_from_db, get_user_stats, 
    delete_user_data, set_notification_interval, get_deadline_by_id
)
from src.bot.states import Registration, AddDeadline, SetNotificationInterval
from src.parser.scraper import parse_deadlines_from_lk

from src.bot.keyboards import (
    get_main_menu_keyboard, get_cancel_keyboard, get_profile_keyboard,
    get_confirm_delete_keyboard, get_deadlines_settings_keyboard,
    get_notification_settings_keyboard, get_confirm_delete_deadline_keyboard
)

import asyncio

# Создание роутера (нужен для организации хэндлеров)
# Хендлер - это функция, которая обрабатывает входящие сообщения и команды.
router = Router()


async def show_main_menu(message: types.Message):
    """Вспомогательная функция для отправки главного меню."""
    await message.answer("Вы в главном меню.", reply_markup=get_main_menu_keyboard())


@router.message(Command("cancel"))
@router.message(F.text == "❌ Отмена")
async def cmd_cancel(message: types.Message, state: FSMContext):
    """Обработчик для отмены любого действия."""
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нечего отменять.")
        await show_main_menu(message)
        return

    await state.clear()
    await message.answer("Действие отменено.")
    await show_main_menu(message)


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        "Я бот-помощник для студентов ГУАП. Что я умею:\n\n"
        "✅ <b>Автоматически</b> проверяю ваш личный кабинет и присылаю уведомления о дедлайнах.\n"
        "✅ По команде /status или кнопке <b>'Посмотреть дедлайны'</b> показываю все актуальные задачи.\n\n"
        "Доступные команды:\n"
        "/start — Начать работу, запуск/переапуск бота\n"
        "/status — Показать дедлайны\n"
        "/help — Cправка по работе бота\n"
        "/cancel — Отменить текущее действие\n"
        "/stop — Остановить работу бота и удалить свои данные"
    )
    await message.answer(help_text, parse_mode="HTML")


# Хэндлер, который срабатывает на "/start"
@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    """Обработчик команды /start."""

    is_new = await add_user(telegram_id=message.from_user.id, username=message.from_user.username)

    if is_new:
        await message.answer(
            "Привет! Я бот для отслеживания дедлайнов в лк ГУАП.\n"
            "🥸 Вижу, ты здесь впервые. Давай пройдем регистрацию!\n\n"
            "[1️⃣/2️⃣] Отправь мне свой логин/почту от личного кабинета.",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(Registration.waiting_for_login)
    else:
        await message.answer(
            "😊 С возвращением! Я уже знаю тебя!\n"
            "👇 Чтобы посмотреть дедлайны, используй соответствующие кнопки.",
            reply_markup=get_main_menu_keyboard()
        )


@router.message(Registration.waiting_for_login, F.text)
async def process_login(message: types.Message, state: FSMContext):
    await state.update_data(login=message.text)
    await message.answer("[2️⃣/2️⃣] Отлично! Теперь введи свой пароль.")
    await state.set_state(Registration.waiting_for_password)


@router.message(Registration.waiting_for_password, F.text)
async def process_password(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    login = user_data.get('login')
    password = message.text

    await message.delete()  # Удаление сообщения с паролем (для безопасности)

    msg_to_delete = await message.answer("Пытаюсь войти в личный кабинет, это может занять минуту...")

    # Парсер - синхронный (использует requests), а бот - асинхронный.
    # Поэтому запуск парсера происходит в отдельном потоке, чтобы не блокировать бота.
    loop = asyncio.get_event_loop()
    new_parsed_deadlines = await loop.run_in_executor(None, parse_deadlines_from_lk, login, password)

    await msg_to_delete.delete()  # Удаление сообщения "Пытаюсь войти..."

    if new_parsed_deadlines is None:
        await message.answer(
            "⛔ Не удалось войти. Скорее всего, логин и/или пароль неверны.\n"
            "🥴 Пожалуйста, попробуй еще раз. Введи логин.",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(Registration.waiting_for_login)
        return

    # Если мы здесь, значит авторизация прошла успешно
    
    # Сохранение учётных данных в БД
    await set_user_credentials(
        telegram_id=message.from_user.id,
        login=login,
        password=password
    )
    
    # Завершение регистрации
    await state.clear()  
    await message.answer(
        "✅️ Отлично!\n"
        "💾 Я успешно вошёл в твой личный кабинет и сохранил твои данные.\n"
        "🤫 Для безопасности я удалил сообщение с паролем из нашего чата.",
        reply_markup=get_main_menu_keyboard()
    )

    if new_parsed_deadlines:
        await update_user_deadlines(message.from_user.id, new_parsed_deadlines)
        deadlines_text = "\n\n".join(
            [f"📚 <b>{d['subject']}</b>\n"
             f"📝 <b>Задание:</b> {d['task']}\n"
             f"🗓️ <b>Срок сдачи:</b> {d['due_date']}" for d in new_parsed_deadlines]
        )
        await message.answer(f"Вот, что я нашёл:\n\n{deadlines_text}", parse_mode="HTML")
    else:
        await message.answer("Пока что я не нашел активных дедлайнов.")


### Основные команды меню

# Команда "/status" и кнопка "Посмотреть дедлайны"
@router.message(Command("status"))
@router.message(F.text == "🚨 Посмотреть дедлайны")
async def show_deadlines(message: types.Message):
    deadlines = await get_user_deadlines_from_db(message.from_user.id)
    if not deadlines:
        await message.answer(
            "🕳 У вас пока нет предстоящих дедлайнов в базе. \n"
            "⏰ Обновление происходит автоматически <u>раз в час</u>.",
            parse_mode="HTML")
        return

    deadlines_text = "⏳ <b>Ваши актуальные дедлайны:</b>\n\n"
    for d in deadlines:
        deadlines_text += (
            f"📚 <b>{d.course_name}</b>\n"
            f"📝 <b>Задание:</b> {d.task_name}\n"
            f"🗓️ <b>Срок сдачи:</b> {d.due_date.strftime('%d.%m.%Y')}\n\n"
        )
    await message.answer(deadlines_text, parse_mode="HTML")

# Кнопка "Мой профиль"
@router.message(F.text == "👤 Мой профиль")
async def show_profile(message: types.Message):
    stats = await get_user_stats(message.from_user.id)
    if not stats:
        await message.answer("⛔ Не удалось найти ваш профиль. Попробуйте /start.")
        return

    profile_text = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"Активных дедлайнов: {stats.get('active_deadlines', 0)}\n"
    )
    await message.answer(profile_text, reply_markup=get_profile_keyboard(), parse_mode="HTML")

# Команда "/stop" для удаления данных
@router.message(Command("stop"))
async def cmd_stop(message: types.Message):
    await message.answer(
        "Вы уверены, что хотите отписаться и удалить все свои данные?\n"
        "Это действие <b><u>необратимо</u></b>.",
        reply_markup=get_confirm_delete_keyboard(),
        parse_mode="HTML"
    )

# Кнопка "Настройка напоминаний"
@router.message(F.text == "🔔 Настройка напоминаний")
async def settings_notifications_menu(message: types.Message):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("⛔ Не удалось найти ваш профиль. Попробуйте /start.")
        return

    await message.answer(
        "🔔 Здесь вы можете настроить уведомления:",
        reply_markup=get_notification_settings_keyboard(user)
    )


async def update_notification_settings_menu(callback: CallbackQuery):
    """Вспомогательная функция для обновления меню настроек."""
    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("⛔ Произошла ошибка, не могу найти ваш профиль.")
        return

    try:
        await callback.message.edit_reply_markup(
            reply_markup=get_notification_settings_keyboard(user)
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer()
        else:
            await callback.answer("⛔ Произошла ошибка при обновлении.")
            print(f"Непредвиденная ошибка: {e}")

# Кнопка "Настройка дедлайнов"
@router.message(F.text == "🛠️ Настройка дедлайнов")
async def settings_deadlines_menu(message: types.Message):
    deadlines = await get_user_deadlines_from_db(message.from_user.id)
    await message.answer(
        "🔧 Здесь вы можете управлять дедлайнами:\nдобавлять собственные или удалять уже имеющиеся.",
        reply_markup=get_deadlines_settings_keyboard(deadlines)
    )


### Обработчики Callback'ов (нажатий на inline-кнопки)

@router.callback_query(F.data == "delete_my_data")
async def on_delete_data(callback: CallbackQuery):
    await callback.message.edit_text(
        "🗑️ Вы уверены, что хотите отписаться и удалить все свои данные?\n"
        "❗️ Это действие <b><u>необратимо</u></b>.",
        reply_markup=get_confirm_delete_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "confirm_delete")
async def on_confirm_delete(callback: CallbackQuery):
    deleted = await delete_user_data(callback.from_user.id)
    if deleted:
        # Убираем клавиатуру главного меню
        from aiogram.types import ReplyKeyboardRemove
        await callback.message.edit_text(
            "🚮 Все ваши данные были удалены! Чтобы снова начать, отправьте /start.",
            reply_markup=None
        )
        # Отправляем новое сообщение, чтобы убрать reply_markup
        await callback.bot.send_message(
            callback.from_user.id,
            "👋 Вы были отписаны.",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        await callback.message.edit_text("⛔ Произошла ошибка при удалении. Попробуйте еще раз позже.", reply_markup=None)
    await callback.answer()


@router.callback_query(F.data == "cancel_delete")
async def on_cancel_delete(callback: CallbackQuery):
    await callback.message.edit_text("❕ Удаление отменено.", reply_markup=None)
    await callback.answer()


@router.callback_query(F.data.startswith("del_deadline_"))
async def delete_deadline_confirm_callback(callback: CallbackQuery):
    """
    Этот хэндлер запрашивает подтверждение на удаление дедлайна.
    """
    # Извлекаем ID дедлайна из callback_data
    deadline_id = int(callback.data.split("_")[2])
    
    # Получаем информацию о дедлайне из БД
    deadline = await get_deadline_by_id(deadline_id)
    
    if not deadline:
        await callback.answer("Этот дедлайн уже удален.", show_alert=True)
        return
    
    # Формируем информативное сообщение
    text = (
        f"Вы уверены, что хотите удалить дедлайн?\n\n"
        f"📚 <b>{deadline.course_name}</b>\n"
        f"📝 {deadline.task_name}\n"
        f"🗓️ {deadline.due_date.strftime('%d.%m.%Y')}"
    )
    
    # Редактируем сообщение, добавляя клавиатуру подтверждения
    await callback.message.edit_text(
        text,
        reply_markup=get_confirm_delete_deadline_keyboard(deadline_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_del_deadline_"))
async def confirm_delete_deadline_callback(callback: CallbackQuery):
    """
    Этот хэндлер срабатывает при подтверждении и окончательно удаляет дедлайн.
    """
    deadline_id = int(callback.data.split("_")[3])
    await delete_deadline_by_id(deadline_id)
    
    # Обновляем исходное меню настроек, чтобы показать, что дедлайн исчез
    deadlines = await get_user_deadlines_from_db(callback.from_user.id)
    await callback.message.edit_text(
        "🚮 Дедлайн удален. Вот обновленный список:",
        reply_markup=get_deadlines_settings_keyboard(deadlines)
    )
    await callback.answer(text="Удалено!", show_alert=False)


@router.callback_query(F.data == "cancel_del_deadline")
async def cancel_delete_deadline_callback(callback: CallbackQuery):
    """
    Этот хэндлер срабатывает при отмене удаления, возвращая пользователя
    в меню настроек дедлайнов.
    """
    deadlines = await get_user_deadlines_from_db(callback.from_user.id)
    await callback.message.edit_text(
        "❕ Удаление отменено. Вы снова в меню управления дедлайнами.",
        reply_markup=get_deadlines_settings_keyboard(deadlines)
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_main_from_settings")
async def back_to_main_menu_callback(callback: CallbackQuery):
    await callback.message.delete()
    await show_main_menu(callback.message)
    await callback.answer()


@router.callback_query(F.data == "toggle_notifications")
async def toggle_notifications_callback(callback: CallbackQuery):
    await toggle_notifications(callback.from_user.id)
    await update_notification_settings_menu(callback)


@router.callback_query(F.data.startswith("toggle_day_"))
async def toggle_day_callback(callback: CallbackQuery):
    day = int(callback.data.split("_")[2])
    await update_notification_days(callback.from_user.id, day)
    await update_notification_settings_menu(callback)

### FSM для настройки интервала уведомлений

@router.callback_query(F.data == "set_interval")
async def set_interval_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "✍ Введите интервал в часах для частых уведомлений:\n"
        "каждые <u>сколько часов</u> будет отправляться уведомление.\n\n"
        "<i>Или введите <b>0</b>, чтобы отключить частые уведомления</i>:",
        parse_mode="HTML"
    )
    await state.set_state(SetNotificationInterval.waiting_for_hours)
    await callback.answer()

@router.message(SetNotificationInterval.waiting_for_hours, F.text)
async def set_interval_hours(message: types.Message, state: FSMContext):
    try:
        hours = int(message.text)
        if not (0 <= hours <= 100):
            raise ValueError
    except ValueError:
        await message.answer("⛔️ Неверный формат. Пожалуйста, введите целое число от 0 до 100.")
        return

    await set_notification_interval(message.from_user.id, hours)
    await state.clear()
    
    # Обновляем меню, чтобы пользователь увидел изменения
    user = await get_user_by_telegram_id(message.from_user.id)
    if user:
        await message.answer(
            "✅ Настройки сохранены!",
            reply_markup=get_notification_settings_keyboard(user)
        )

### FSM для добавления нового дедлайна

@router.message(Command("add"))
@router.callback_query(F.data == "add_deadline")
async def add_deadline_start(event: Union[types.Message, CallbackQuery], state: FSMContext):
    """
    Универсальный хэндлер для начала добавления дедлайна.
    Срабатывает как на команду /add, так и на нажатие inline-кнопки.
    """
    text = "[1️⃣/3️⃣] Введите название предмета:"
    
    # Проверяем, как была вызвана функция
    if isinstance(event, types.Message):
        # Если через команду /add, то отправляем новое сообщение
        await event.answer(text, reply_markup=get_cancel_keyboard())
    elif isinstance(event, CallbackQuery):
        # Удаляем старое сообщение с кнопками настроек
        await event.message.delete()
        # Отправляем новое сообщение с кнопкой отмены
        await event.message.answer(text, reply_markup=get_cancel_keyboard())
        # Отвечаем на callback, чтобы убрать "часики"
        await event.answer()
        
    # Устанавливаем состояние в любом случае
    await state.set_state(AddDeadline.waiting_for_course_name)


@router.message(AddDeadline.waiting_for_course_name, F.text)
async def add_deadline_course(message: types.Message, state: FSMContext):
    await state.update_data(course_name=message.text)
    await message.answer("[2️⃣/3️⃣] Теперь введите название задания:")
    await state.set_state(AddDeadline.waiting_for_task_name)


@router.message(AddDeadline.waiting_for_task_name, F.text)
async def add_deadline_task(message: types.Message, state: FSMContext):
    await state.update_data(task_name=message.text)
    await message.answer("[3️⃣/3️⃣] Теперь введите дату сдачи в формате ДД.ММ.ГГГГ (например, 25.12.2025):")
    await state.set_state(AddDeadline.waiting_for_due_date)


@router.message(AddDeadline.waiting_for_due_date, F.text)
async def add_deadline_date(message: types.Message, state: FSMContext):
    try:
        due_date = datetime.strptime(message.text, "%d.%m.%Y")
    except ValueError:
        await message.answer("⛔️ Неверный формат даты. Пожалуйста, введите дату в формате ДД.ММ.ГГГГ:")
        return

    user_data = await state.get_data()
    await add_custom_deadline(
        telegram_id=message.from_user.id,
        course=user_data.get("course_name"),
        task=user_data.get("task_name"),
        due_date=due_date
    )

    await state.clear()
    await message.answer("✅ Новый дедлайн успешно добавлен!")
    await show_main_menu(message)
