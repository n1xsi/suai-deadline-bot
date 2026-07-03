#!/bin/sh
# Точка входа для Docker-контейнера
# (если миграции уже применены, alembic ничего не делает)
set -e

echo "Applying database migrations..."
alembic upgrade head

echo "Starting bot..."
exec python -m src.bot.main_bot
