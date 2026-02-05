from environs import Env
from os import getenv

env = Env()
env.read_env()

BOT_TOKEN = env.str("BOT_TOKEN")
ADMIN_ID = env.int("ADMIN_ID")

# Если переменная окружения задана (на сервере) - берем её, если нет (локально) - кладём в корень в папку db
DB_PATH = getenv("DB_PATH", "database/database.db")

ENCRYPTION_KEY = env.str("ENCRYPTION_KEY", default=None)
