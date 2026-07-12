#!/bin/sh
# Точка входа для Docker-контейнера
# (если миграции уже применены, alembic ничего не делает)
set -e

# Ревизия, соответствующая схеме
BASELINE_REVISION="0001_initial_schema"

# Уведомление админа в Telegram об критических ошибках на этапе миграций (когда бот не может стартовать)
notify_admin() {
    python -c '
import os
import sys
import urllib.parse
import urllib.request

token = os.getenv("BOT_TOKEN")
chat_id = os.getenv("ADMIN_ID")
if not (token and chat_id):
    sys.exit(0)

data = urllib.parse.urlencode({"chat_id": chat_id, "text": sys.argv[1]}).encode()
try:
    urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data, timeout=10)
except Exception as error:
    print(f"Не удалось уведомить админа: {error}", file=sys.stderr)
' "$1" || true
}

# Защита от падения контейнера при попытке применить миграции к базе, созданной до Alembic
NEEDS_STAMP=$(python -c '
import os
import sqlite3

db_path = os.getenv("DB_PATH", "database/database.db")
if not os.path.exists(db_path):
    print("skip")
    raise SystemExit

conn = sqlite3.connect(db_path)
tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = ?", ("table",))}
conn.close()

print("stamp" if "alembic_version" not in tables and tables & {"users", "deadlines"} else "skip")
' || echo "check_failed")

if [ "$NEEDS_STAMP" = "stamp" ]; then
    echo "Schema exists without alembic_version, stamping database as $BASELINE_REVISION..."
    alembic stamp "$BASELINE_REVISION"
fi

echo "Applying database migrations..."
if ! alembic upgrade head; then
    notify_admin "❗ CRITICAL: не удалось применить миграции БД. Бот не запущен."
    exit 1
fi

echo "Starting bot..."
exec python -m src.bot.main_bot
