"""
Конфігурація бота.
Токен та ID адміністратора (тобто ваш ID) беруться зі змінних середовища,
щоб не зберігати секрети прямо в коді.
"""
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError(
        "Не знайдено BOT_TOKEN. Створіть файл .env на основі .env.example "
        "і вкажіть там токен, отриманий від @BotFather."
    )

# ID адміністратора(ів) — тобто вас. Можна вказати кілька через кому в .env
_admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in _admin_ids_raw.split(",") if x.strip()]

if not ADMIN_IDS:
    raise RuntimeError(
        "Не знайдено ADMIN_IDS у .env. Дізнатись свій Telegram ID можна, "
        "написавши боту @userinfobot."
    )

DB_PATH = os.getenv("DB_PATH", "orders.db")
