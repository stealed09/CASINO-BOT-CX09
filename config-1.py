import os
from dotenv import load_dotenv

load_dotenv()

# ── Core bot settings ──────────────────────────────────────────────────────────
BOT_TOKEN     = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
MAIN_ADMIN_ID = int(os.getenv("MAIN_ADMIN_ID", "123456789"))

# ── ADMIN_IDS ─────────────────────────────────────────────────────────────────
# Railway me set karo: ADMIN_IDS=123456789,987654321 (comma separated)
# Ya sirf MAIN_ADMIN_ID set karo — wo automatically ADMIN_IDS me aa jayega
_raw = os.getenv("ADMIN_IDS", "")
if _raw.strip():
    ADMIN_IDS = set()
    for _id in _raw.split(","):
        try:
            ADMIN_IDS.add(int(_id.strip()))
        except ValueError:
            pass
    ADMIN_IDS.add(MAIN_ADMIN_ID)  # always include main admin
else:
    # Fallback: just use MAIN_ADMIN_ID
    ADMIN_IDS = {MAIN_ADMIN_ID}

# ── Database ───────────────────────────────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", "data/casino.db")

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_FILE = os.getenv("LOG_FILE", "logs/bot.log")

# ── Game defaults ──────────────────────────────────────────────────────────────
REFERRAL_PERCENT = float(os.getenv("REFERRAL_PERCENT", "5.0"))


# ── BotState (used by bot.py escrow system) ────────────────────────────────────
class BotState:
    def __init__(self):
        self.log_group_id      = None
        self.sub_admins        = set()
        self.fee_percent       = 1.0
        self.required_bio      = None
        self.oxapay_key        = None
        self.deals             = {}
        self.group_to_deal     = {}
        self.dispute_admins    = {}
        self.telethon_client   = None
        self.api_id            = None
        self.api_hash          = None
        self.phone             = None
        self._pending_telethon = None
        self._waiting_otp      = False

state = BotState()
