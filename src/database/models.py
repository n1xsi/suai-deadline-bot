from sqlalchemy import BigInteger, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs
from datetime import datetime

# Базовый класс для моделей, который добавляет асинхронные возможности
class Base(AsyncAttrs, DeclarativeBase):
    pass

# Модель Пользователя
class User(Base):
    __tablename__ = 'users' # Название таблицы в БД

    # Колонки таблицы
    id: Mapped[int] = mapped_column(primary_key=True) # Первичный ключ
    telegram_id = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(32), nullable=True) # username в telegram может отсутствовать
    
    # Пока без хранения логина/пароля, добавим их позже, когда напишем шифрование
    # encrypted_login_lk: Mapped[str] = mapped_column(String(255), nullable=True)
    # encrypted_password_lk: Mapped[str] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now()) # Дата создания записи

# Модель Дедлайна
class Deadline(Base):
    __tablename__ = 'deadlines'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(nullable=False) # Внешний ключ на user.id
    course_name: Mapped[str] = mapped_column(String(100), nullable=False)
    task_name: Mapped[str] = mapped_column(String(255), nullable=False)
    due_date: Mapped[datetime] = mapped_column(nullable=False)