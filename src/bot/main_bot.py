from src.config import BOT_TOKEN
from src.bot.handlers import router as main_router
from src.database.engine import create_tables
from src.scheduler.tasks import update_all_deadlines, send_deadline_notifications

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import asyncio
import logging


async def set_main_menu_commands(bot: Bot):
    """
    Создаёт и устанавливает меню с командами для бота.
    """
    # Создаем список команд с описаниями
    main_menu_commands = [
        BotCommand(command="/start", description="Запустить/перезапустить бота"),
        BotCommand(command="/status", description="Показать актуальные дедлайны"),
        BotCommand(command="/help", description="Справка по работе бота"),
        BotCommand(command="/cancel", description="Отменить текущее действие"),
        BotCommand(command="/stop", description="❌ Остановить работу бота и удалить свои данные ❌")
    ]
    
    # Устанавливаем команды для бота
    await bot.set_my_commands(main_menu_commands)


async def main():
    """
    Основная функция, которая запускает бота
    """
    # Логирование, чтобы видеть информацию о работе бота в консоли
    logging.basicConfig(level=logging.INFO)

    # Создание таблиц в БД перед запуском бота
    await create_tables()

    # Инициализация бота с токеном
    bot = Bot(token=BOT_TOKEN)
    
    # Инициализция команд для бота
    await set_main_menu_commands(bot)

    # Диспетчер - будет принимать апдейты от Telegram и передавать их хэндлерам
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(main_router)

    # Инициализиация планировщика
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

    # Добавление задачи на обновление дедлайнов ('interval' - запускать с интервалом)
    scheduler.add_job(update_all_deadlines, trigger='interval', hours=1)

    # Добавление задачи на отправку уведомлений
    scheduler.add_job(send_deadline_notifications, trigger='interval', hours=1, args=(bot,))

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
