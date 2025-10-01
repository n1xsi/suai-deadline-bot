from loguru import logger
from aiogram import Bot

import sys
import asyncio
import logging


class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


class TelegramSink:
    def __init__(self, bot: Bot, chat_id: int):
        self.bot = bot
        self.chat_id = chat_id

    def __call__(self, message):
        record = message.record
        if record["level"].name in ("ERROR", "CRITICAL"):
            text = (
                f"❗ {record['level'].name}\n"
                f"File: {record['file'].name}:{record['line']}\n"
                f"Function: {record['function']}\n"
                f"Message: {record['message']}"
            )
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.bot.send_message(self.chat_id, text))
            else:
                loop.run_until_complete(self.bot.send_message(self.chat_id, text))


def init_logger(bot: Bot, chat_id: int, level: str = "DEBUG"):
    # Переопределение логгера для aiogram и asyncio 
    logging.getLogger('aiogram').setLevel(logging.DEBUG)
    logging.getLogger('aiogram').addHandler(InterceptHandler())
    logging.getLogger('asyncio').setLevel(logging.DEBUG)
    logging.getLogger('asyncio').addHandler(InterceptHandler())

    # Создание логгера и добавление обработчика
    logger.remove()
    logger.add("logs/bot_{time:YYYY-MM-DD}.log", rotation="1 week", retention="3 week")
    logger.add(sys.stdout, level=level)
    logger.add(TelegramSink(bot, chat_id), level="ERROR")
    
    logger.info("Логирование настроено")
    return logger
