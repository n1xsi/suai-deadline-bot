from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
import asyncio # Понадобится для запуска синхронного парсера в отдельном потоке

from src.database.queries import add_user, set_user_credentials, update_user_deadlines
from src.bot.states import Registration
from src.parser.scraper import parse_deadlines_from_lk

# Создание роутера (нужны, чтобы разбивать логику по файлам)
router = Router()

# Хэндлер, который срабатывает на "/start" 
@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    """Обработчик команды /start."""
    
    is_new = await add_user(telegram_id=message.from_user.id, username=message.from_user.username)

    if is_new:
        await message.answer(
            "Привет! Я бот для отслеживания дедлайнов ГУАП.\n"
            "Вижу, ты здесь впервые. Давай пройдем регистрацию.\n\n"
            "Отправь мне свой логин от личного кабинета."
        )
        await state.set_state(Registration.waiting_for_login)
    else:
        await message.answer(
            "С возвращением! Я уже знаю тебя.\n"
            "Чтобы посмотреть дедлайны, используй соответствующие кнопки." # Добавим их позже
        )

@router.message(Registration.waiting_for_login, F.text)
async def process_login(message: types.Message, state: FSMContext):
    await state.update_data(login=message.text)
    await message.answer("Отлично! Теперь введи свой пароль.")
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
            "Не удалось войти. Скорее всего, логин и/или пароль неверны.\n"
            "Пожалуйста, попробуй еще раз. Введи логин."
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
        "Отлично! Я успешно вошёл в твой личный кабинет и сохранил твои данные.\n" 
        "Для безопасности я удалил сообщение с паролем из нашего чата."
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