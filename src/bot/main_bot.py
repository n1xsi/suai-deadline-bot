from src.config import BOT_TOKEN
from src.bot.handlers import router as main_router
from src.database.engine import create_tables

from aiogram import Bot, Dispatcher
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
    bot = Bot(token=BOT_TOKEN)

    # Диспетчер. Будет принимать апдейты от Telegram и передавать их хэндлерам 
    dp = Dispatcher()

    # Подключаение роутера с нашими хэндлерами
    dp.include_router(main_router)

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