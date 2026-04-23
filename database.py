import aiosqlite
import asyncio
import os
from datetime import datetime
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

            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT DEFAULT '',
                    balance REAL DEFAULT 0.0,
                    referral_id INTEGER DEFAULT NULL,
                    referral_earnings REAL DEFAULT 0.0,
                    total_wagered REAL DEFAULT 0.0,
                    join_date TEXT DEFAULT '',
                    bonus_eligible INTEGER DEFAULT 0,
                    bonus_warned INTEGER DEFAULT 0,
                    warn_time TEXT DEFAULT NULL,
                    last_weekly TEXT DEFAULT NULL,
                    last_monthly TEXT DEFAULT NULL,
                    currency_mode TEXT DEFAULT 'inr',
                    currency_change_requested TEXT DEFAULT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    amount REAL NOT NULL,
                    currency TEXT DEFAULT 'INR',
                    status TEXT DEFAULT 'completed',
                    date TEXT NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS withdrawals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    currency TEXT DEFAULT 'INR',
                    upi_id TEXT DEFAULT '',
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
                    amount REAL NOT NULL,
                    currency TEXT DEFAULT 'INR',
                    txn_id TEXT DEFAULT '',
                    screenshot_id TEXT DEFAULT '',
                    status TEXT DEFAULT 'pending',
                    date TEXT NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS crypto_wallets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    balance REAL DEFAULT 0.0,
                    UNIQUE(user_id, symbol)
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
                CREATE TABLE IF NOT EXISTS swap_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    from_currency TEXT NOT NULL,
                    to_currency TEXT NOT NULL,
                    from_amount REAL NOT NULL,
                    to_amount REAL NOT NULL,
                    rate REAL NOT NULL,
                    status TEXT DEFAULT 'completed',
                    date TEXT NOT NULL
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
                    amount REAL NOT NULL,
                    currency TEXT DEFAULT 'INR',
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

            defaults = [
                ("min_withdrawal", "100"),
                ("withdraw_enabled", "1"),
                ("weekly_bonus", "50"),
                ("monthly_bonus", "200"),
                ("bonus_mode", "fixed"),
                ("upi_id", "notset@upi"),
                ("upi_qr", ""),
                ("star_payment_id", ""),
                ("bot_username_tag", ""),
                ("deposit_tax", "5"),
                ("withdrawal_tax", "0"),
                ("referral_percent", "1"),
                ("crypto_to_inr_rate", "85"),
                ("inr_to_crypto_rate", "0.012"),
                ("swap_fee_percent", "1"),
            ]
            for key, value in defaults:
                await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))

            # Default USDT TRC20
            await db.execute("""
                INSERT OR IGNORE INTO crypto_currencies (symbol, name, network, wallet_address, enabled, added_at)
                VALUES ('USDT', 'Tether USD', 'TRC20', 'TYourWalletAddressHere', 1, ?)
            """, (datetime.now().isoformat(),))

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
                        (user_id, username, balance, referral_id, referral_earnings,
                         total_wagered, join_date, bonus_eligible, bonus_warned, warn_time,
                         last_weekly, last_monthly, currency_mode, currency_change_requested)
                        VALUES (?, ?, 0.0, ?, 0.0, 0.0, ?, 0, 0, NULL, NULL, NULL, 'inr', NULL)""",
                        (user_id, username or "", referral_id, datetime.now().isoformat())
                    )
                    await db.commit()
            return True
        except Exception as e:
            logger.error(f"create_user error: {e}")
            return False

    async def update_balance(self, user_id: int, amount: float) -> bool:
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
                    await db.commit()
            return True
        except Exception as e:
            logger.error(f"update_balance error: {e}")
            return False

    async def set_balance(self, user_id: int, amount: float) -> bool:
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute("UPDATE users SET balance = ? WHERE user_id = ?", (amount, user_id))
                    await db.commit()
            return True
        except Exception as e:
            logger.error(f"set_balance error: {e}")
            return False

    async def update_wagered(self, user_id: int, amount: float):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET total_wagered = total_wagered + ? WHERE user_id = ?", (amount, user_id))
            await db.commit()

    async def update_username(self, user_id: int, username: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET username = ? WHERE user_id = ?", (username or "", user_id))
            await db.commit()

    async def set_currency_mode(self, user_id: int, mode: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET currency_mode = ? WHERE user_id = ?", (mode, user_id))
            await db.commit()

    async def request_currency_change(self, user_id: int, requested_mode: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET currency_change_requested = ? WHERE user_id = ?",
                (requested_mode, user_id)
            )
            await db.commit()

    async def approve_currency_change(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT currency_change_requested FROM users WHERE user_id=?", (user_id,)) as cur:
                row = await cur.fetchone()
            if row and row[0]:
                await db.execute(
                    "UPDATE users SET currency_mode=?, currency_change_requested=NULL WHERE user_id=?",
                    (row[0], user_id)
                )
                await db.commit()
                return row[0]
            return None

    async def get_pending_currency_changes(self) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE currency_change_requested IS NOT NULL"
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]

    # ─── TRANSACTIONS ──────────────────────────────────────────────────────────

    async def add_transaction(self, user_id: int, type_: str, amount: float, status: str = "completed", currency: str = "INR"):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO transactions (user_id, type, amount, currency, status, date) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, type_, amount, currency, status, datetime.now().isoformat())
            )
            await db.commit()

    async def get_transactions(self, user_id: int, limit: int = 10) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM transactions WHERE user_id = ? ORDER BY date DESC LIMIT ?", (user_id, limit)
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]

    # ─── WITHDRAWALS ───────────────────────────────────────────────────────────

    async def create_withdrawal(self, user_id: int, amount: float, currency: str = "INR",
                                 upi_id: str = "", crypto_address: str = "", crypto_network: str = "") -> int:
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                cur = await db.execute(
                    """INSERT INTO withdrawals
                    (user_id, amount, currency, upi_id, crypto_address, crypto_network, status, date)
                    VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)""",
                    (user_id, amount, currency, upi_id, crypto_address, crypto_network, datetime.now().isoformat())
                )
                await db.commit()
                return cur.lastrowid

    async def get_pending_withdrawals(self) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM withdrawals WHERE status='pending' ORDER BY date ASC") as cur:
                return [dict(r) for r in await cur.fetchall()]

    async def update_withdrawal_status(self, wid: int, status: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE withdrawals SET status=? WHERE id=?", (status, wid))
            await db.commit()

    async def get_withdrawal(self, wid: int) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM withdrawals WHERE id=?", (wid,)) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    # ─── DEPOSITS ──────────────────────────────────────────────────────────────

    async def create_deposit(self, user_id: int, method: str, amount: float,
                              currency: str = "INR", txn_id: str = "", screenshot_id: str = "") -> int:
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                cur = await db.execute(
                    """INSERT INTO deposits
                    (user_id, method, amount, currency, txn_id, screenshot_id, status, date)
                    VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)""",
                    (user_id, method, amount, currency, txn_id, screenshot_id, datetime.now().isoformat())
                )
                await db.commit()
                return cur.lastrowid

    async def update_deposit_screenshot(self, did: int, screenshot_id: str, txn_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE deposits SET screenshot_id=?, txn_id=? WHERE id=?", (screenshot_id, txn_id, did))
            await db.commit()

    async def get_pending_deposits(self) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM deposits WHERE status='pending' ORDER BY date ASC") as cur:
                return [dict(r) for r in await cur.fetchall()]

    async def update_deposit_status(self, did: int, status: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE deposits SET status=? WHERE id=?", (status, did))
            await db.commit()

    async def get_deposit(self, did: int) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM deposits WHERE id=?", (did,)) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    # ─── CRYPTO WALLETS ────────────────────────────────────────────────────────

    async def get_crypto_balance(self, user_id: int, symbol: str) -> float:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT balance FROM crypto_wallets WHERE user_id=? AND symbol=?", (user_id, symbol.upper())
            ) as cur:
                row = await cur.fetchone()
                return row[0] if row else 0.0

    async def update_crypto_balance(self, user_id: int, symbol: str, amount: float) -> bool:
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute(
                        """INSERT INTO crypto_wallets (user_id, symbol, balance)
                        VALUES (?, ?, ?)
                        ON CONFLICT(user_id, symbol) DO UPDATE SET balance = balance + excluded.balance""",
                        (user_id, symbol.upper(), amount)
                    )
                    await db.commit()
            return True
        except Exception as e:
            logger.error(f"update_crypto_balance error: {e}")
            return False

    async def get_all_crypto_balances(self, user_id: int) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM crypto_wallets WHERE user_id=?", (user_id,)) as cur:
                return [dict(r) for r in await cur.fetchall()]

    # ─── CRYPTO CURRENCIES ─────────────────────────────────────────────────────

    async def get_all_cryptos(self, enabled_only: bool = True) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            q = "SELECT * FROM crypto_currencies WHERE enabled=1" if enabled_only else "SELECT * FROM crypto_currencies"
            async with db.execute(q) as cur:
                return [dict(r) for r in await cur.fetchall()]

    async def get_crypto(self, symbol: str) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM crypto_currencies WHERE symbol=?", (symbol.upper(),)) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def add_crypto_currency(self, symbol: str, name: str, network: str, wallet_address: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO crypto_currencies (symbol, name, network, wallet_address, enabled, added_at)
                VALUES (?, ?, ?, ?, 1, ?)""",
                (symbol.upper(), name, network, wallet_address, datetime.now().isoformat())
            )
            await db.commit()

    async def toggle_crypto(self, symbol: str, enabled: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE crypto_currencies SET enabled=? WHERE symbol=?", (enabled, symbol.upper()))
            await db.commit()

    async def update_crypto_address(self, symbol: str, address: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE crypto_currencies SET wallet_address=? WHERE symbol=?", (address, symbol.upper()))
            await db.commit()

    # ─── SWAP ──────────────────────────────────────────────────────────────────

    async def add_swap_record(self, user_id: int, from_currency: str, to_currency: str,
                               from_amount: float, to_amount: float, rate: float):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO swap_requests
                (user_id, from_currency, to_currency, from_amount, to_amount, rate, status, date)
                VALUES (?, ?, ?, ?, ?, ?, 'completed', ?)""",
                (user_id, from_currency, to_currency, from_amount, to_amount, rate, datetime.now().isoformat())
            )
            await db.commit()

    # ─── SETTINGS ──────────────────────────────────────────────────────────────

    async def get_setting(self, key: str) -> Optional[str]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT value FROM settings WHERE key=?", (key,)) as cur:
                row = await cur.fetchone()
                return row["value"] if row else None

    async def set_setting(self, key: str, value: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
            await db.commit()

    async def get_all_users(self) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users") as cur:
                return [dict(r) for r in await cur.fetchall()]

    # ─── LOCKS ─────────────────────────────────────────────────────────────────

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
        except Exception as e:
            logger.error(f"lock_balance error: {e}")
            return False

    async def unlock_balance(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM balance_locks WHERE user_id=?", (user_id,))
            await db.commit()

    async def is_balance_locked(self, user_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT user_id FROM balance_locks WHERE user_id=?", (user_id,)) as cur:
                return await cur.fetchone() is not None

    # ─── REFERRAL ──────────────────────────────────────────────────────────────

    async def update_referral_earnings(self, referral_id: int, amount: float):
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE users SET referral_earnings=referral_earnings+?, balance=balance+? WHERE user_id=?",
                    (amount, amount, referral_id)
                )
                await db.commit()

    async def get_referral_count(self, user_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM users WHERE referral_id=?", (user_id,)) as cur:
                row = await cur.fetchone()
                return row[0] if row else 0

    # ─── BONUS ─────────────────────────────────────────────────────────────────

    async def set_bonus_eligible(self, user_id: int, value: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET bonus_eligible=? WHERE user_id=?", (value, user_id))
            await db.commit()

    async def set_warn(self, user_id: int, warned: int, warn_time: Optional[str]):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET bonus_warned=?, warn_time=? WHERE user_id=?",
                (warned, warn_time, user_id)
            )
            await db.commit()

    async def reset_bonus_progress(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET bonus_eligible=0, bonus_warned=0, warn_time=NULL, join_date=?, last_weekly=NULL, last_monthly=NULL WHERE user_id=?",
                (datetime.now().isoformat(), user_id)
            )
            await db.commit()

    async def update_last_bonus(self, user_id: int, bonus_type: str):
        col = "last_weekly" if bonus_type == "weekly" else "last_monthly"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"UPDATE users SET {col}=? WHERE user_id=?", (datetime.now().isoformat(), user_id))
            await db.commit()

    # ─── REDEEM CODES ──────────────────────────────────────────────────────────

    async def create_redeem_code(self, code: str, amount: float, admin_id: int, currency: str = "INR"):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO redeem_codes (code, amount, currency, created_by, created_at) VALUES (?, ?, ?, ?, ?)",
                (code.upper(), amount, currency, admin_id, datetime.now().isoformat())
            )
            await db.commit()

    async def get_redeem_code(self, code: str) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM redeem_codes WHERE code=?", (code.upper(),)) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def use_redeem_code(self, code: str, user_id: int) -> bool:
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT * FROM redeem_codes WHERE code=? AND used_by IS NULL", (code.upper(),)
                ) as cur:
                    row = await cur.fetchone()
                if not row:
                    return False
                await db.execute(
                    "UPDATE redeem_codes SET used_by=?, used_at=? WHERE code=?",
                    (user_id, datetime.now().isoformat(), code.upper())
                )
                await db.commit()
                return True

    async def get_all_redeem_codes(self) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM redeem_codes ORDER BY created_at DESC LIMIT 30") as cur:
                return [dict(r) for r in await cur.fetchall()]

    # ─── SUPPORT TICKETS ───────────────────────────────────────────────────────

    async def create_support_ticket(self, user_id: int, message: str) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "INSERT INTO support_tickets (user_id, message, status, date) VALUES (?, ?, 'open', ?)",
                (user_id, message, datetime.now().isoformat())
            )
            await db.commit()
            return cur.lastrowid

    async def update_ticket_admin_msg(self, ticket_id: int, admin_message_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE support_tickets SET admin_message_id=? WHERE id=?",
                (admin_message_id, ticket_id)
            )
            await db.commit()

    async def get_ticket(self, ticket_id: int) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM support_tickets WHERE id=?", (ticket_id,)) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None


db = Database()
