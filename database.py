import aiosqlite
import asyncio
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from config import DB_PATH
from utils.logger import logger


class Database:
    def __init__(self):
        self.db_path = DB_PATH
        self._lock = asyncio.Lock()

    async def init(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA foreign_keys=ON")

            # Users table — token_balance is the ONLY balance now
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT DEFAULT '',
                    token_balance REAL DEFAULT 0.0,
                    referral_id INTEGER DEFAULT NULL,
                    referral_earnings REAL DEFAULT 0.0,
                    total_wagered REAL DEFAULT 0.0,
                    daily_wagered REAL DEFAULT 0.0,
                    daily_wager_date TEXT DEFAULT '',
                    weekly_wagered REAL DEFAULT 0.0,
                    weekly_wager_date TEXT DEFAULT '',
                    monthly_wagered REAL DEFAULT 0.0,
                    monthly_wager_date TEXT DEFAULT '',
                    join_date TEXT DEFAULT '',
                    bonus_eligible INTEGER DEFAULT 0,
                    bonus_warned INTEGER DEFAULT 0,
                    warn_time TEXT DEFAULT NULL,
                    last_weekly TEXT DEFAULT NULL,
                    last_monthly TEXT DEFAULT NULL,
                    custom_deposit_tax REAL DEFAULT -1,
                    custom_withdraw_tax REAL DEFAULT -1,
                    is_banned INTEGER DEFAULT 0
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    amount REAL NOT NULL,
                    currency TEXT DEFAULT 'TOKEN',
                    status TEXT DEFAULT 'completed',
                    date TEXT NOT NULL
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS withdrawals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token_amount REAL NOT NULL,
                    method TEXT DEFAULT 'upi',
                    upi_id TEXT DEFAULT '',
                    crypto_currency TEXT DEFAULT '',
                    crypto_address TEXT DEFAULT '',
                    crypto_network TEXT DEFAULT '',
                    status TEXT DEFAULT 'pending',
                    date TEXT NOT NULL
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS deposits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    method TEXT NOT NULL,
                    inr_amount REAL DEFAULT 0.0,
                    stars_amount INTEGER DEFAULT 0,
                    crypto_currency TEXT DEFAULT '',
                    crypto_amount REAL DEFAULT 0.0,
                    token_credited REAL DEFAULT 0.0,
                    txn_id TEXT DEFAULT '',
                    screenshot_id TEXT DEFAULT '',
                    nowpayments_id TEXT DEFAULT '',
                    status TEXT DEFAULT 'pending',
                    date TEXT NOT NULL
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS crypto_currencies (
                    symbol TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    network TEXT NOT NULL,
                    wallet_address TEXT NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    added_at TEXT NOT NULL
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS balance_locks (
                    user_id INTEGER PRIMARY KEY,
                    locked_amount REAL DEFAULT 0.0
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS redeem_codes (
                    code TEXT PRIMARY KEY,
                    token_amount REAL NOT NULL,
                    created_by INTEGER NOT NULL,
                    used_by INTEGER DEFAULT NULL,
                    used_at TEXT DEFAULT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS support_tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    admin_message_id INTEGER DEFAULT NULL,
                    status TEXT DEFAULT 'open',
                    date TEXT NOT NULL
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS nowpayments_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    deposit_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    payment_id TEXT NOT NULL,
                    pay_currency TEXT NOT NULL,
                    pay_amount REAL NOT NULL,
                    pay_address TEXT NOT NULL,
                    status TEXT DEFAULT 'waiting',
                    created_at TEXT NOT NULL,
                    UNIQUE(payment_id)
                )
            """)

            defaults = [
                ("min_withdrawal_tokens", "100"),
                ("withdraw_enabled", "1"),
                ("weekly_bonus_tokens", "50"),
                ("monthly_bonus_tokens", "200"),
                ("bonus_mode", "fixed"),
                ("bonus_wager_percent_weekly", "1"),
                ("bonus_wager_percent_monthly", "2"),
                ("upi_id", "notset@upi"),
                ("upi_qr", ""),
                ("bot_username_tag", ""),
                ("deposit_tax", "10"),
                ("withdrawal_tax", "5"),
                ("referral_percent", "1"),
                ("inr_to_token_rate", "1"),
                ("stars_to_token_rate", "1"),
                ("crypto_to_token_rate_USDT", "85"),
                ("crypto_to_token_rate_BTC", "8500000"),
                ("crypto_to_token_rate_ETH", "300000"),
                ("nowpayments_enabled", "0"),
                ("oxapay_merchant_key", ""),
                ("game_tax_percent", "5"),
                ("limbo_win_percent", "20"),
                ("usd_to_token_rate", "85"),
            ]
            for key, value in defaults:
                await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))

            await db.execute("""
                INSERT OR IGNORE INTO crypto_currencies (symbol, name, network, wallet_address, enabled, added_at)
                VALUES ('USDT', 'Tether USD', 'TRC20', 'TYourWalletAddressHere', 1, ?)
            """, (datetime.now().isoformat(),))

            await db.execute("""
                CREATE TABLE IF NOT EXISTS sub_admins (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT DEFAULT '',
                    added_by INTEGER NOT NULL,
                    added_at TEXT NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS fake_leaderboard (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    display_name TEXT NOT NULL,
                    total_wagered REAL NOT NULL
                )
            """)
            try:
                await db.execute("ALTER TABLE withdrawals ADD COLUMN address_confirm TEXT DEFAULT ''")
            except:
                pass
            # ── NEW FEATURE TABLES ────────────────────────────────────────
            await db.execute("""
                CREATE TABLE IF NOT EXISTS provably_fair (
                    user_id INTEGER PRIMARY KEY,
                    server_seed TEXT NOT NULL,
                    client_seed TEXT NOT NULL,
                    nonce INTEGER DEFAULT 0
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS rakeback_claims (
                    user_id INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    claimed_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, type)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS mission_progress (
                    user_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    wager REAL DEFAULT 0,
                    games_played INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    crash_plays INTEGER DEFAULT 0,
                    claimed_missions TEXT DEFAULT '[]',
                    PRIMARY KEY (user_id, date)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS pvp_duels (
                    id TEXT PRIMARY KEY,
                    creator_id INTEGER NOT NULL,
                    opponent_id INTEGER,
                    game_type TEXT NOT NULL,
                    bet REAL NOT NULL,
                    winner_id INTEGER,
                    status TEXT DEFAULT 'waiting',
                    created_at TEXT NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS lootbox_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    case_type TEXT NOT NULL,
                    reward_label TEXT NOT NULL,
                    reward_amount REAL NOT NULL,
                    opened_at TEXT NOT NULL
                )
            """)
            new_defaults = [
                ("rakeback_weekly_pct", "1"),
                ("rain_enabled", "1"),
                ("pvp_house_fee", "5"),
                ("vip_enabled", "1"),
                ("rakeback_enabled", "1"),
                ("missions_enabled", "1"),
                ("lootbox_enabled", "1"),
                ("crash_enabled", "1"),
                ("slots_enabled", "1"),
                ("live_feed_enabled", "1"),
                ("live_feed_mix_fake", "1"),
                ("crash_max_bet", "10000"),
                ("crash_min_bet", "10"),
                ("slots_max_bet", "5000"),
                ("slots_min_bet", "10"),
            ]
            for key, value in new_defaults:
                await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))
            for col, default in [
                ("total_wins", "0"),
                ("total_losses", "0"),
                ("biggest_win", "0.0"),
            ]:
                try:
                    await db.execute(f"ALTER TABLE users ADD COLUMN {col} INTEGER DEFAULT {default}")
                except:
                    pass

            fake_entries = [
                ("Arjun_🎰", 485200), ("Priya_💎", 321500), ("RajKumar", 298000),
                ("Lucky77", 265000), ("Sneha_Win", 198500),
            ]
            for name, wager in fake_entries:
                await db.execute(
                    "INSERT OR IGNORE INTO fake_leaderboard (display_name, total_wagered) VALUES (?, ?)",
                    (name, wager)
                )
            await db.commit()
        logger.info("Database initialized.")

    # ─── USER ──────────────────────────────────────────────────────────────────

    async def get_user(self, user_id: int) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def get_user_by_username(self, username: str) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (username.lstrip("@"),)
            ) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def create_user(self, user_id: int, username: str, referral_id: Optional[int] = None) -> bool:
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute(
                        """INSERT OR IGNORE INTO users
                        (user_id, username, token_balance, referral_id, referral_earnings,
                         total_wagered, daily_wagered, weekly_wagered, monthly_wagered,
                         join_date, bonus_eligible, bonus_warned, warn_time,
                         last_weekly, last_monthly, custom_deposit_tax, custom_withdraw_tax, is_banned)
                        VALUES (?, ?, 0.0, ?, 0.0, 0.0, 0.0, 0.0, 0.0, ?, 0, 0, NULL, NULL, NULL, -1, -1, 0)""",
                        (user_id, username or "", referral_id, datetime.now().isoformat())
                    )
                    await db.commit()
            return True
        except Exception as e:
            logger.error(f"create_user error: {e}")
            return False

    async def get_all_users(self) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE is_banned = 0") as cur:
                return [dict(r) for r in await cur.fetchall()]

    async def get_all_users_admin(self) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users") as cur:
                return [dict(r) for r in await cur.fetchall()]

    async def update_token_balance(self, user_id: int, amount: float) -> bool:
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute(
                        "UPDATE users SET token_balance = token_balance + ? WHERE user_id = ?",
                        (amount, user_id)
                    )
                    await db.commit()
            return True
        except Exception as e:
            logger.error(f"update_token_balance error: {e}")
            return False

    async def set_token_balance(self, user_id: int, amount: float) -> bool:
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute(
                        "UPDATE users SET token_balance = ? WHERE user_id = ?",
                        (amount, user_id)
                    )
                    await db.commit()
            return True
        except Exception as e:
            logger.error(f"set_token_balance error: {e}")
            return False

    async def update_wagered(self, user_id: int, amount: float):
        now = datetime.now()
        today = now.date().isoformat()
        week_start = (now - timedelta(days=now.weekday())).date().isoformat()
        month_start = now.replace(day=1).date().isoformat()

        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                user = await self.get_user(user_id)
                if not user:
                    return

                # Reset daily if new day
                daily = user.get("daily_wagered", 0.0)
                if user.get("daily_wager_date", "") != today:
                    daily = 0.0
                    await db.execute("UPDATE users SET daily_wagered=0.0, daily_wager_date=? WHERE user_id=?", (today, user_id))

                # Reset weekly
                weekly = user.get("weekly_wagered", 0.0)
                if user.get("weekly_wager_date", "") != week_start:
                    weekly = 0.0
                    await db.execute("UPDATE users SET weekly_wagered=0.0, weekly_wager_date=? WHERE user_id=?", (week_start, user_id))

                # Reset monthly
                monthly = user.get("monthly_wagered", 0.0)
                if user.get("monthly_wager_date", "") != month_start:
                    monthly = 0.0
                    await db.execute("UPDATE users SET monthly_wagered=0.0, monthly_wager_date=? WHERE user_id=?", (month_start, user_id))

                await db.execute(
                    """UPDATE users SET
                        total_wagered = total_wagered + ?,
                        daily_wagered = ? + ?,
                        weekly_wagered = ? + ?,
                        monthly_wagered = ? + ?
                    WHERE user_id = ?""",
                    (amount, daily, amount, weekly, amount, monthly, amount, user_id)
                )
                await db.commit()

            # ── Auto-update mission wager progress ─────────────────────
            await self.update_mission_progress(user_id, wager=amount)

    async def update_username(self, user_id: int, username: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET username = ? WHERE user_id = ?", (username or "", user_id))
            await db.commit()

    async def get_effective_deposit_tax(self, user_id: int) -> float:
        user = await self.get_user(user_id)
        if user and user.get("custom_deposit_tax", -1) >= 0:
            return float(user["custom_deposit_tax"])
        return float(await self.get_setting("deposit_tax") or "10")

    async def get_effective_withdraw_tax(self, user_id: int) -> float:
        user = await self.get_user(user_id)
        if user and user.get("custom_withdraw_tax", -1) >= 0:
            return float(user["custom_withdraw_tax"])
        base_tax = float(await self.get_setting("withdrawal_tax") or "5")
        # Apply VIP discount
        vip_enabled = await self.get_setting("vip_enabled")
        if vip_enabled == "1" and user:
            from vip import get_vip_level
            vip = get_vip_level(user.get("total_wagered", 0))
            discount = vip.get("withdraw_tax_discount", 0.0)
            base_tax = max(0.0, base_tax - discount)
        return base_tax

    async def set_user_custom_tax(self, user_id: int, deposit_tax: float = -1, withdraw_tax: float = -1):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET custom_deposit_tax=?, custom_withdraw_tax=? WHERE user_id=?",
                (deposit_tax, withdraw_tax, user_id)
            )
            await db.commit()

    async def set_ban(self, user_id: int, banned: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET is_banned=? WHERE user_id=?", (banned, user_id))
            await db.commit()

    # ─── WAGER LEADERBOARD ─────────────────────────────────────────────────────

    async def get_top_wagers(self, period: str = "lifetime", limit: int = 10) -> List[Dict]:
        col_map = {
            "daily": "daily_wagered",
            "weekly": "weekly_wagered",
            "monthly": "monthly_wagered",
            "lifetime": "total_wagered",
        }
        col = col_map.get(period, "total_wagered")
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                f"SELECT user_id, username, {col} as wagered, token_balance FROM users ORDER BY {col} DESC LIMIT ?",
                (limit,)
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]

    # ─── BONUS ELIGIBLE ────────────────────────────────────────────────────────

    async def set_bonus_eligible(self, user_id: int, val: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET bonus_eligible=? WHERE user_id=?", (val, user_id))
            await db.commit()

    async def set_warn(self, user_id: int, warned: int, warn_time: Optional[str]):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET bonus_warned=?, warn_time=? WHERE user_id=?", (warned, warn_time, user_id))
            await db.commit()

    async def reset_bonus_progress(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET bonus_eligible=0, bonus_warned=0, warn_time=NULL WHERE user_id=?",
                (user_id,)
            )
            await db.commit()

    async def update_referral_earnings(self, user_id: int, amount: float):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET referral_earnings = referral_earnings + ? WHERE user_id = ?",
                (amount, user_id)
            )
            await db.commit()

    async def set_last_bonus(self, user_id: int, bonus_type: str):
        col = "last_weekly" if bonus_type == "weekly" else "last_monthly"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"UPDATE users SET {col}=? WHERE user_id=?", (datetime.now().isoformat(), user_id))
            await db.commit()

    # ─── TRANSACTIONS ──────────────────────────────────────────────────────────

    async def add_transaction(self, user_id: int, type_: str, amount: float, status: str = "completed", currency: str = "TOKEN"):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO transactions (user_id, type, amount, currency, status, date) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, type_, amount, currency, status, datetime.now().isoformat())
            )
            await db.commit()
        # Track wins/losses only for game transactions (not tips, deposits, bonuses etc.)
        GAME_WIN_TYPES = {"crash_win", "slots_win", "pvp_win"}
        GAME_LOSS_TYPES = {"crash_loss", "slots_loss", "pvp_loss"}
        if type_ in GAME_WIN_TYPES:
            await self.record_game_result(user_id, True, amount)
        elif type_ in GAME_LOSS_TYPES:
            await self.record_game_result(user_id, False, 0)

    async def get_transactions(self, user_id: int, limit: int = 10) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM transactions WHERE user_id = ? ORDER BY date DESC LIMIT ?", (user_id, limit)
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]

    # ─── WITHDRAWALS ───────────────────────────────────────────────────────────

    async def create_withdrawal(self, user_id: int, token_amount: float, method: str = "upi",
                                upi_id: str = "", crypto_currency: str = "",
                                crypto_address: str = "", crypto_network: str = "") -> int:
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                cur = await db.execute(
                    """INSERT INTO withdrawals
                    (user_id, token_amount, method, upi_id, crypto_currency, crypto_address, crypto_network, status, date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
                    (user_id, token_amount, method, upi_id, crypto_currency, crypto_address, crypto_network, datetime.now().isoformat())
                )
                await db.commit()
                return cur.lastrowid

    async def get_withdrawal(self, wid: int) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM withdrawals WHERE id = ?", (wid,)) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def get_pending_withdrawals(self) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM withdrawals WHERE status='pending' ORDER BY date ASC") as cur:
                return [dict(r) for r in await cur.fetchall()]

    async def update_withdrawal_status(self, wid: int, status: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE withdrawals SET status=? WHERE id=?", (status, wid))
            await db.commit()

    # ─── DEPOSITS ──────────────────────────────────────────────────────────────

    async def create_deposit(self, user_id: int, method: str, inr_amount: float = 0.0,
                             stars_amount: int = 0, crypto_currency: str = "",
                             crypto_amount: float = 0.0) -> int:
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                cur = await db.execute(
                    """INSERT INTO deposits
                    (user_id, method, inr_amount, stars_amount, crypto_currency, crypto_amount, status, date)
                    VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)""",
                    (user_id, method, inr_amount, stars_amount, crypto_currency, crypto_amount, datetime.now().isoformat())
                )
                await db.commit()
                return cur.lastrowid

    async def get_deposit(self, did: int) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM deposits WHERE id = ?", (did,)) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def get_pending_deposits(self) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM deposits WHERE status='pending' ORDER BY date ASC") as cur:
                return [dict(r) for r in await cur.fetchall()]

    async def update_deposit_status(self, did: int, status: str, token_credited: float = 0.0,
                                    txn_id: str = "", screenshot_id: str = ""):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE deposits SET status=?, token_credited=?, txn_id=?, screenshot_id=? WHERE id=?",
                (status, token_credited, txn_id, screenshot_id, did)
            )
            await db.commit()

    async def update_deposit_screenshot(self, did: int, screenshot_id: str, txn_id: str = ""):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE deposits SET screenshot_id=?, txn_id=? WHERE id=?",
                (screenshot_id, txn_id, did)
            )
            await db.commit()

    # ─── NOWPAYMENTS ──────────────────────────────────────────────────────────

    async def create_nowpayments_order(self, deposit_id: int, user_id: int, payment_id: str,
                                       pay_currency: str, pay_amount: float, pay_address: str) -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """INSERT OR IGNORE INTO nowpayments_orders
                    (deposit_id, user_id, payment_id, pay_currency, pay_amount, pay_address, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'waiting', ?)""",
                    (deposit_id, user_id, payment_id, pay_currency, pay_amount, pay_address, datetime.now().isoformat())
                )
                await db.commit()
            return True
        except Exception as e:
            logger.error(f"create_nowpayments_order error: {e}")
            return False

    async def get_nowpayments_order(self, payment_id: str) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM nowpayments_orders WHERE payment_id=?", (payment_id,)
            ) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def update_nowpayments_status(self, payment_id: str, status: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE nowpayments_orders SET status=? WHERE payment_id=?", (status, payment_id))
            await db.commit()

    # ─── CRYPTO ────────────────────────────────────────────────────────────────

    async def get_all_cryptos(self, enabled_only: bool = True) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            q = "SELECT * FROM crypto_currencies WHERE enabled=1" if enabled_only else "SELECT * FROM crypto_currencies"
            async with db.execute(q) as cur:
                return [dict(r) for r in await cur.fetchall()]

    async def get_crypto(self, symbol: str) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM crypto_currencies WHERE symbol=?", (symbol,)) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def add_crypto(self, symbol: str, name: str, network: str, address: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO crypto_currencies (symbol, name, network, wallet_address, enabled, added_at) VALUES (?, ?, ?, ?, 1, ?)",
                (symbol, name, network, address, datetime.now().isoformat())
            )
            await db.commit()

    async def update_crypto_address(self, symbol: str, address: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE crypto_currencies SET wallet_address=? WHERE symbol=?", (address, symbol))
            await db.commit()

    async def toggle_crypto(self, symbol: str, enabled: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE crypto_currencies SET enabled=? WHERE symbol=?", (enabled, symbol))
            await db.commit()

    # ─── BALANCE LOCKS ─────────────────────────────────────────────────────────

    async def lock_balance(self, user_id: int, amount: float) -> bool:
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute(
                        "INSERT OR REPLACE INTO balance_locks (user_id, locked_amount) VALUES (?, ?)",
                        (user_id, amount)
                    )
                    await db.commit()
            return True
        except:
            return False

    async def unlock_balance(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM balance_locks WHERE user_id=?", (user_id,))
            await db.commit()

    async def is_balance_locked(self, user_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT user_id FROM balance_locks WHERE user_id=?", (user_id,)) as cur:
                return (await cur.fetchone()) is not None

    # ─── REDEEM CODES ──────────────────────────────────────────────────────────

    async def create_redeem_code(self, code: str, token_amount: float, created_by: int) -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO redeem_codes (code, token_amount, created_by, created_at) VALUES (?, ?, ?, ?)",
                    (code, token_amount, created_by, datetime.now().isoformat())
                )
                await db.commit()
            return True
        except:
            return False

    async def use_redeem_code(self, code: str, user_id: int) -> Optional[float]:
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT * FROM redeem_codes WHERE code=?", (code,)) as cur:
                    row = await cur.fetchone()
                if not row:
                    return None
                row = dict(row)
                if row["used_by"] is not None:
                    return -1.0  # already used
                await db.execute(
                    "UPDATE redeem_codes SET used_by=?, used_at=? WHERE code=?",
                    (user_id, datetime.now().isoformat(), code)
                )
                await db.commit()
                return float(row["token_amount"])

    async def get_all_redeem_codes(self) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM redeem_codes ORDER BY created_at DESC") as cur:
                return [dict(r) for r in await cur.fetchall()]

    # ─── SUPPORT ───────────────────────────────────────────────────────────────

    async def create_support_ticket(self, user_id: int, message: str) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "INSERT INTO support_tickets (user_id, message, status, date) VALUES (?, ?, 'open', ?)",
                (user_id, message, datetime.now().isoformat())
            )
            await db.commit()
            return cur.lastrowid

    async def set_ticket_admin_msg_id(self, ticket_id: int, msg_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE support_tickets SET admin_message_id=? WHERE id=?", (msg_id, ticket_id))
            await db.commit()

    async def get_ticket(self, ticket_id: int) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM support_tickets WHERE id=?", (ticket_id,)) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    # ─── SETTINGS ──────────────────────────────────────────────────────────────

    async def get_setting(self, key: str) -> Optional[str]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT value FROM settings WHERE key=?", (key,)) as cur:
                row = await cur.fetchone()
                return row[0] if row else None

    async def set_setting(self, key: str, value: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
            await db.commit()

    # ─── ADMIN USER DETAIL ─────────────────────────────────────────────────────

    async def get_user_full_detail(self, user_id: int) -> Optional[Dict]:
        user = await self.get_user(user_id)
        if not user:
            return None
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT COUNT(*) as dep_count, SUM(token_credited) as total_dep FROM deposits WHERE user_id=? AND status='approved'",
                (user_id,)
            ) as cur:
                dep_row = dict(await cur.fetchone())
            async with db.execute(
                "SELECT COUNT(*) as wd_count, SUM(token_amount) as total_wd FROM withdrawals WHERE user_id=? AND status='paid'",
                (user_id,)
            ) as cur:
                wd_row = dict(await cur.fetchone())
            async with db.execute(
                "SELECT COUNT(*) as ref_count FROM users WHERE referral_id=?", (user_id,)
            ) as cur:
                ref_row = dict(await cur.fetchone())
        user["dep_count"] = dep_row["dep_count"] or 0
        user["total_deposited"] = dep_row["total_dep"] or 0.0
        user["wd_count"] = wd_row["wd_count"] or 0
        user["total_withdrawn"] = wd_row["total_wd"] or 0.0
        user["referral_count"] = ref_row["ref_count"] or 0
        return user


    # ─── SUB ADMINS ────────────────────────────────────────────────────────────

    async def add_sub_admin(self, user_id: int, username: str, added_by: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO sub_admins (user_id, username, added_by, added_at) VALUES (?, ?, ?, ?)",
                (user_id, username, added_by, datetime.now().isoformat())
            )
            await db.commit()

    async def remove_sub_admin(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM sub_admins WHERE user_id=?", (user_id,))
            await db.commit()

    async def is_sub_admin(self, user_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT 1 FROM sub_admins WHERE user_id=?", (user_id,)) as cur:
                return await cur.fetchone() is not None

    async def get_all_sub_admins(self) -> list:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM sub_admins") as cur:
                return [dict(r) for r in await cur.fetchall()]

    # ─── FAKE LEADERBOARD ──────────────────────────────────────────────────────

    async def get_fake_leaderboard(self) -> list:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM fake_leaderboard ORDER BY total_wagered DESC") as cur:
                return [dict(r) for r in await cur.fetchall()]

    async def add_fake_leader(self, display_name: str, wager: float):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO fake_leaderboard (display_name, total_wagered) VALUES (?, ?)",
                (display_name, wager)
            )
            await db.commit()

    async def remove_fake_leader(self, fid: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM fake_leaderboard WHERE id=?", (fid,))
            await db.commit()


    # ─── MISSION PROGRESS ─────────────────────────────────────────────────────

    async def get_mission_progress(self, user_id: int) -> dict:
        from datetime import date
        today = date.today().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM mission_progress WHERE user_id=? AND date=?", (user_id, today)
            ) as cur:
                row = await cur.fetchone()
            if not row:
                return {"wager": 0, "games_played": 0, "wins": 0, "crash_plays": 0, "claimed_missions": "[]"}
            return dict(row)

    async def update_mission_progress(self, user_id: int, **kwargs):
        from datetime import date
        today = date.today().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO mission_progress (user_id, date) VALUES (?, ?)
                ON CONFLICT(user_id, date) DO NOTHING
            """, (user_id, today))
            for col, val in kwargs.items():
                if col == "claimed_missions":
                    await db.execute(
                        f"UPDATE mission_progress SET {col}=? WHERE user_id=? AND date=?",
                        (val, user_id, today)
                    )
                else:
                    await db.execute(
                        f"UPDATE mission_progress SET {col}={col}+? WHERE user_id=? AND date=?",
                        (val, user_id, today)
                    )
            await db.commit()

    # ─── PLAYER STATS ──────────────────────────────────────────────────────────

    async def record_game_result(self, user_id: int, won: bool, amount: float):
        """Track wins/losses/biggest win for profile stats."""
        async with aiosqlite.connect(self.db_path) as db:
            if won:
                await db.execute("""
                    UPDATE users SET
                        total_wins = total_wins + 1,
                        biggest_win = MAX(biggest_win, ?)
                    WHERE user_id=?
                """, (amount, user_id))
            else:
                await db.execute("UPDATE users SET total_losses = total_losses + 1 WHERE user_id=?", (user_id,))
            await db.commit()
        # Also update mission progress
        if won:
            await self.update_mission_progress(user_id, wins=1, games_played=1)
        else:
            await self.update_mission_progress(user_id, games_played=1)

    # ─── LOOTBOX ───────────────────────────────────────────────────────────────

    async def log_lootbox(self, user_id: int, case_type: str, reward_label: str, reward_amount: float):
        from datetime import datetime
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO lootbox_history (user_id, case_type, reward_label, reward_amount, opened_at) VALUES (?,?,?,?,?)",
                (user_id, case_type, reward_label, reward_amount, datetime.now().isoformat())
            )
            await db.commit()


db = Database()
