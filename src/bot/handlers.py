from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from src.database.queries import add_user

# Создание роутера (нужны, чтобы разбивать логику по файлам)
router = Router() 

# Хэндлер, который срабатывает на "/start" 
@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start."""
    
    # Вызываем функцию добавления пользователя
    # message.from_user.id - это telegram_id
    # message.from_user.username - это его username
    is_new = await add_user(telegram_id=message.from_user.id, username=message.from_user.username)

    if is_new:
        # Если пользователь новый
        await message.answer(
            "Привет! Я бот для отслеживания дедлайнов ГУАП.\n"
            "Вижу, ты здесь впервые. Давай пройдем регистрацию.\n\n"
            "Отправь мне свой логин от личного кабинета."
        )
    else:
        # Если пользователь уже есть в базе
        await message.answer(
            "С возвращением! Я уже знаю тебя.\n"
            "Чтобы посмотреть дедлайны, используй соответствующие кнопки." # Добавим их позже
        )