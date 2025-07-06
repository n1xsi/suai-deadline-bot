from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

# Создание роутера (нужны, чтобы разбивать логику по файлам)
router = Router() 

# Хэндлер, который срабатывает на "/start" 
@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я бот для отслеживания дедлайнов заданий в лк ГУАП!\n"
        "Чтобы начать, мне понадобится доступ к твоему личному кабинету.\n\n"
        "Отправь мне свой логин." # Пока просто текст, логику чут-чут позже завезём
    )