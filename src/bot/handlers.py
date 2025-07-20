from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
import asyncio

from src.database.queries import add_user, set_user_credentials, update_user_deadlines
from src.bot.states import Registration
from src.parser.scraper import parse_deadlines_from_lk

from src.bot.keyboards import get_main_menu_keyboard, get_cancel_keyboard, get_profile_keyboard, get_confirm_delete_keyboard
from src.database.queries import (
    add_user, set_user_credentials, update_user_deadlines,
    get_user_deadlines_from_db, get_user_stats, delete_user_data
)

# Создание роутера (нужны, чтобы разбивать логику по файлам)
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
        "/start - Начать работу\n"
        "/status - Показать дедлайны\n"
        "/stop - Остановить работу бота и удалить свои данные\n"
        "/help - Помощь\n"
        "/cancel - Отменить текущее действие"
    )
    await message.answer(help_text, parse_mode="HTML")


# Хэндлер, который срабатывает на "/start" 
@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    """Обработчик команды /start."""
    
    is_new = await add_user(telegram_id=message.from_user.id, username=message.from_user.username)

    if is_new:
        await message.answer(
            "Привет! Я бот для отслеживания дедлайнов ГУАП.\n"
            "Вижу, ты здесь впервые. Давай пройдем регистрацию.\n\n"
            "[1️⃣/2️⃣] Отправь мне свой логин от личного кабинета.",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(Registration.waiting_for_login)
    else:
        await message.answer(
            "С возвращением! Я уже знаю тебя!\n"
            "Чтобы посмотреть дедлайны, используй соответствующие кнопки.",
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

    await message.delete() # Удаляем сообщение с паролем для безопасности
    await message.answer("Спасибо! Пытаюсь войти в личный кабинет, это может занять минуту...")

    # ВАЖНО: Парсер - синхронный (использует requests), а бот - асинхронный.
    # Чтобы не блокировать бота, мы запускаем парсер в отдельном потоке.
    loop = asyncio.get_event_loop()
    deadlines = await loop.run_in_executor(
        None, parse_deadlines_from_lk, login, password
    )

    if deadlines is None:
        await message.answer(
            "⛔ Не удалось войти. Скорее всего, логин и/или пароль неверны.\n"
            "Пожалуйста, попробуй еще раз. Введи логин.",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(Registration.waiting_for_login)
        return

    # Если мы здесь, значит авторизация прошла успешно
    
    # Сохраняем учетные данные в БД
    await set_user_credentials(
        telegram_id=message.from_user.id,
        login=login,
        password=password
    )
    
    await state.clear() # Завершаем регистрацию
    await message.answer(
        "✅️Отлично!\n"
        "💾Я успешно вошёл в твой личный кабинет и сохранил твои данные.\n" 
        "🤫Для безопасности я удалил сообщение с паролем из нашего чата.",
        reply_markup=get_main_menu_keyboard() 
    ) 
    
    # Сохраняем найденные дедлайны в БД
    if deadlines:
        await update_user_deadlines(message.from_user.id, deadlines)
    
    if deadlines:
        deadlines_text = "\n\n".join(
            [f"📚 <b>{d['subject']}</b>\n"
            f"📝 <b>Задание:</b> {d['task']}\n"
            f"🗓️ <b>Срок сдачи:</b> {d['due_date']}" for d in deadlines]
        )
        await message.answer(f"Вот что я нашел:\n\n{deadlines_text}", parse_mode="HTML")
    else:
        await message.answer("Пока что я не нашел активных дедлайнов.")
        

### Основные команды меню

# Команда /status и кнопка "Посмотреть дедлайны"
@router.message(Command("status"))
@router.message(F.text == "🚨 Посмотреть дедлайны")
async def show_deadlines(message: types.Message):
    deadlines = await get_user_deadlines_from_db(message.from_user.id)
    if not deadlines:
        await message.answer(
            "У вас пока нет предстоящих дедлайнов в базе. "
            "Обновление происходит автоматически <u>раз в час</u>.",
            parse_mode="HTML")
        return

    deadlines_text = "✨ <b>Ваши актуальные дедлайны:</b>\n\n" 
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
        await message.answer("Не удалось найти ваш профиль. Попробуйте /start.")
        return
    
    profile_text = (
        f"👤 <b>Ваш профиль</b>\n\n" 
        f"Активных дедлайнов: {stats.get('active_deadlines', 0)}\n"
        # f"Личных дедлайнов: {stats.get('custom_deadlines', 0)}" # для будущего
    )
    await message.answer(profile_text, reply_markup=get_profile_keyboard(), parse_mode="HTML")

# Команда /stop для удаления данных
@router.message(Command("stop"))
async def cmd_stop(message: types.Message):
    await message.answer(
        "Вы уверены, что хотите отписаться и удалить все свои данные?\n"
        "Это действие <b><u>необратимо</u></b>.",
        reply_markup=get_confirm_delete_keyboard(),
        parse_mode="HTML"
    )

### Обработчики Callback'ов (нажатий на inline-кнопки)

@router.callback_query(F.data == "delete_my_data")
async def on_delete_data(callback: CallbackQuery):
    await callback.message.edit_text(
        "Вы уверены, что хотите отписаться и удалить все свои данные?\n"
        "Это действие <b><u>необратимо</u></b>.",
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
            "Все ваши данные были удалены! Чтобы снова начать, отправьте /start.",
            reply_markup=None
        )
        # Отправляем новое сообщение, чтобы убрать reply_markup
        await callback.bot.send_message(
            callback.from_user.id,
            "Вы были отписаны.",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        await callback.message.edit_text("Произошла ошибка при удалении. Попробуйте еще раз позже.", reply_markup=None)
    await callback.answer()

@router.callback_query(F.data == "cancel_delete")
async def on_cancel_delete(callback: CallbackQuery):
    await callback.message.edit_text("Удаление отменено.", reply_markup=None)
    await callback.answer()

# Остальные хэндлеры (help, FSM) можно оставить как есть, но нужно убедиться,
# что они возвращают правильное меню - get_main_menu_keyboard()