from src.config import BOT_TOKEN
from src.bot.handlers import router as main_router
from src.database.engine import create_tables

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio
import logging

async def main():
    """
    Основная функция, которая запускает бота
    """
    # Логирование, чтобы видеть информацию о работе бота в консоли 
    logging.basicConfig(level=logging.INFO)
    
    # Перед запуском бота создаём таблицы в БД
    await create_tables()

    # Объект бота
    bot = Bot(token=BOT_TOKEN, parse_mode="HTML")

    # Диспетчер. Будет принимать апдейты от Telegram и передавать их хэндлерам 
    dp = Dispatcher(storage=MemoryStorage())
    
    # Подключаение роутера с хэндлерами
    dp.include_router(main_router)
    
    # Инициализиация планировщика
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    # scheduler.add_job(...) # Здесь будем добавлять наши задачи
    
    # Запуск планировщика
    scheduler.start()

    # Запуск бота
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")