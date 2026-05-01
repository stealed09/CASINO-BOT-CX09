import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN     = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
MAIN_ADMIN_ID = int(os.getenv("MAIN_ADMIN_ID", "123456789"))

class BotState:
    def __init__(self):
        self.log_group_id     = None
        self.sub_admins       = set()
        self.fee_percent      = 1.0
        self.required_bio     = None
        self.oxapay_key       = None
        self.deals            = {}
        self.group_to_deal    = {}
        self.dispute_admins   = {}
        self.telethon_client  = None
        # Telethon creds set via bot panel
        self.api_id           = None
        self.api_hash         = None
        self.phone            = None
        self._pending_telethon = None
        self._waiting_otp     = False

state = BotState()
