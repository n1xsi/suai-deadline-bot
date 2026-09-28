from typing import Optional
from html import escape

from aiogram.types import LinkPreviewOptions

# Ссылки на задания не должны разворачиваться в превью и раздувать сообщение
NO_LINK_PREVIEW = LinkPreviewOptions(is_disabled=True)


def task_link(task_name: str, task_url: Optional[str] = None) -> str:
    """
    Оформляет название задания как ссылку на него в личном кабинете.

    Если ссылки нет (записи, созданные до появления поля task_url), возвращается
    просто экранированное название. Экранирование обязательно: символы < и &
    в названиях из ЛК ломают разметку сообщения с parse_mode="HTML".
    """
    name = escape(task_name or "")
    return f'<a href="{escape(task_url)}">{name}</a>' if task_url else name
