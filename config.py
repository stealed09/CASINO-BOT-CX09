import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "0").split(",") if x.strip()]

# NowPayments
NOWPAYMENTS_API_KEY = os.getenv("NOWPAYMENTS_API_KEY", "")
NOWPAYMENTS_IPN_SECRET = os.getenv("NOWPAYMENTS_IPN_SECRET", "")
NOWPAYMENTS_API_URL = "https://api.nowpayments.io/v1"

WIN_MULTIPLIER = 2.0
TAX_PERCENT = 0.10
COOLDOWN_SECONDS = 3
DB_PATH = os.getenv("DB_PATH", "/data/casino.db")
LOG_FILE = "bot.log"
