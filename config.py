import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "0").split(",") if x.strip()]
REFERRAL_PERCENT = 0.0001  # 0.01% of bet amount

WIN_MULTIPLIER = 2.0
TAX_PERCENT = 0.10
DEPOSIT_TAX = 0.05
COOLDOWN_SECONDS = 3
DB_PATH = "/tmp/casino.db"
LOG_FILE = "bot.log"
