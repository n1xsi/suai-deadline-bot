from src.config import BOT_TOKEN
from src.bot.handlers import router as main_router
from src.database.engine import create_tables
from src.scheduler.tasks import update_all_deadlines, send_deadline_notifications

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

    bot = Bot(token=BOT_TOKEN)

    # Диспетчер - будет принимать апдейты от Telegram и передавать их хэндлерам 
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(main_router)
    
    # Инициализиация планировщика
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    
    # Добавление задачи на обновление дедлайнов
    # hours=1 - запуск каждый час.
    scheduler.add_job(update_all_deadlines, trigger='interval', hour=1)
    
    # Добавление задачи на отправку уведомлений ('interval' - запускать с интервалом)
    # hours=3 - запуск каждые 3 часа. bot передается в задачу как аргумент.
    scheduler.add_job(send_deadline_notifications, trigger='interval', hours=3, args=(bot,))
    
    """
    ### Тест системы уведомлений
    await asyncio.sleep(2) 
    await send_deadline_notifications(bot)
    """
    
    
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