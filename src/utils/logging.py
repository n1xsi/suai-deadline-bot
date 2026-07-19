from loguru import logger
from aiogram import Bot

import sys
import time
import asyncio
import inspect
import logging
import traceback

# Telegram не принимает сообщения длиннее 4096 символов
MAX_MESSAGE_LENGTH = 4096

# Обрыв связи при long polling - обычная ситуация, поэтому единичный сбой не повод писать админу
TRANSIENT_ERROR_MARKERS = ("Failed to fetch updates",)

# Сколько подряд идущих сетевых сбоев считать уже не блипом, а реальной проблемой
TRANSIENT_ALERT_THRESHOLD = 5

# Если сетевых сбоев не было столько секунд - считаем, что связь восстановилась
TRANSIENT_RESET_AFTER = 300


class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Поиск кадра, из которого была вызвана запись в лог для вывода места ошибки
        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


class TelegramSink:
    def __init__(self, bot: Bot, chat_id: int):
        self.bot = bot
        self.chat_id = chat_id
        self._pending = set()
        self._transient_count = 0
        self._transient_last = 0.0

    def _check_transient(self, message: str) -> tuple[bool, int]:
        """
        Отслеживает сетевые сбои long polling, о которых не нужно писать администратору.

        :param message: Текст записи лога
        :return: (пропустить ли отправку, число сбоев подряд); для обычных ошибок - (False, 0)
        """
        if not any(marker in message for marker in TRANSIENT_ERROR_MARKERS):
            return False, 0

        now = time.monotonic()
        # Если с прошлого сбоя прошло много времени - связь успела восстановиться, счёт начинается заново
        if now - self._transient_last > TRANSIENT_RESET_AFTER:
            self._transient_count = 0
        self._transient_last = now
        self._transient_count += 1

        # Уведомление уходит ровно на пороговом сбое: пока связь не восстановится, счётчик
        # продолжает расти, поэтому на одну серию обрывов приходится одно сообщение
        return self._transient_count != TRANSIENT_ALERT_THRESHOLD, self._transient_count

    async def _safe_send_log(self, text: str):
        try:
            await self.bot.send_message(self.chat_id, text)
        except Exception as e:
            # Если Telegram недоступен (Bad Gateway и прочие спамящие ошибки) - просто игнорируем
            # Ошибка всё равно запишется в файл logs/bot_...log
            pass

    def __call__(self, message):
        record = message.record
        if record["level"].name in ("ERROR", "CRITICAL"):
            skip, transient_count = self._check_transient(record["message"])
            if skip:
                return

            text = (
                f"❗ {record['level'].name}\n"
                f"File: {record['file'].name}:{record['line']}\n"
                f"Function: {record['function']}\n"
                f"Message: {record['message']}"
            )

            # Порог сработал - сообщаем, что сбой не одиночный, а повторяется
            if transient_count:
                text += (
                    f"\n\n⚠ Сбоев подряд: {transient_count}. Бот продолжает работу "
                    f"и повторяет попытки; следующее уведомление придёт только после "
                    f"восстановления связи и новой серии сбоев."
                )

            exception = record["exception"]
            if exception:
                tb = "".join(traceback.format_exception(
                    exception.type, exception.value, exception.traceback
                )).strip()
                available = MAX_MESSAGE_LENGTH - len(text) - len("\n\nTraceback:\n")
                if available > 0: 
                    if len(tb) > available:
                        # "Хвост" traceback'а информативнее начала: там само исключение и место сбоя
                        tb = "..." + tb[-(available - 3):]
                    text += f"\n\nTraceback:\n{tb}"

            text = text[:MAX_MESSAGE_LENGTH]

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                asyncio.run(self._safe_send_log(text))
            else:
                # Ссылка на задачу сохраняется, иначе сборщик мусора может уничтожить её до отправки сообщения
                task = loop.create_task(self._safe_send_log(text))
                self._pending.add(task)
                task.add_done_callback(self._pending.discard)


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
