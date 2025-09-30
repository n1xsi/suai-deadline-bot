from environs import Env

env = Env()
env.read_env()

BOT_TOKEN = env.str("BOT_TOKEN")
ADMIN_ID = env.int("ADMIN_ID")

DB_PATH = "src/database/database.db"

ENCRYPTION_KEY = env.str("ENCRYPTION_KEY", default=None)
