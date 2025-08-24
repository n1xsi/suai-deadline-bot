from datetime import datetime

from sqlalchemy import Integer, BigInteger, String, Boolean, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs

# Базовый класс для моделей, который добавляет асинхронные возможности
class Base(AsyncAttrs, DeclarativeBase):
    pass

# Модель Пользователя
class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(32), nullable=True)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=True)

    encrypted_login_lk: Mapped[str] = mapped_column(String(255), nullable=True)
    encrypted_password_lk: Mapped[str] = mapped_column(String(255), nullable=True)

    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default='true')
    notification_days: Mapped[str] = mapped_column(String, default="1,3,7", server_default='1,3,7')
    notification_interval_hours: Mapped[int] = mapped_column(Integer, default=0, server_default='0')

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

# Модель Дедлайна
class Deadline(Base):
    __tablename__ = 'deadlines'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(nullable=False)
    course_name: Mapped[str] = mapped_column(String(100), nullable=False)
    task_name: Mapped[str] = mapped_column(String(255), nullable=False)
    due_date: Mapped[datetime] = mapped_column(nullable=False)

    is_custom: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')