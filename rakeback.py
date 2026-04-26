"""
Rakeback / Lossback System
- Daily rakeback: % of daily wager returned
- Weekly rakeback: % of weekly wager returned
- Lossback: compensation for heavy losers
All rates pulled from DB settings or VIP level.
"""

from datetime import datetime, date
from typing import Dict, Optional
import aiosqlite


async def calculate_daily_rakeback(user: Dict, vip_level: Dict, db_path: str) -> float:
    """Return unclaimed daily rakeback amount."""
    daily_wagered = user.get("daily_wagered", 0)
    rate = vip_level["cashback_pct"] / 100.0
    return round(daily_wagered * rate, 4)


async def calculate_weekly_rakeback(user: Dict, rakeback_rate: float) -> float:
    """Return weekly rakeback amount based on weekly_wagered."""
    weekly_wagered = user.get("weekly_wagered", 0)
    rate = rakeback_rate / 100.0
    return round(weekly_wagered * rate, 4)


async def get_rakeback_status(user_id: int, db_path: str) -> Dict:
    """Return last claim timestamps for daily and weekly rakeback."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT key, value FROM settings WHERE key IN ('rb_daily_last_claim', 'rb_weekly_last_claim')"
        ) as cur:
            rows = await cur.fetchall()
        # Per-user rakeback claim times stored as user_{id}_rb_daily etc.
        async with db.execute(
            "SELECT key, value FROM rakeback_claims WHERE user_id=?", (user_id,)
        ) as cur:
            rows = await cur.fetchall()
        result = {}
        for row in rows:
            result[row["key"]] = row["value"]
        return result


async def can_claim_daily(user_id: int, db_path: str) -> bool:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT claimed_at FROM rakeback_claims WHERE user_id=? AND type='daily'", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return True
        last = datetime.fromisoformat(row["claimed_at"]).date()
        return last < date.today()


async def can_claim_weekly(user_id: int, db_path: str) -> bool:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT claimed_at FROM rakeback_claims WHERE user_id=? AND type='weekly'", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return True
        last = datetime.fromisoformat(row["claimed_at"])
        diff = datetime.now() - last
        return diff.days >= 7


async def record_claim(user_id: int, claim_type: str, db_path: str):
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            INSERT INTO rakeback_claims (user_id, type, claimed_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, type) DO UPDATE SET claimed_at=excluded.claimed_at
        """, (user_id, claim_type, datetime.now().isoformat()))
        await db.commit()


def rakeback_menu_text(
    user: Dict,
    vip_level: Dict,
    daily_amount: float,
    weekly_amount: float,
    can_daily: bool,
    can_weekly: bool,
    rakeback_rate: float,
) -> str:
    SEP = "─" * 24
    return (
        f"♻️ <b>RAKEBACK CENTER</b>\n{SEP}\n"
        f"{vip_level['badge']} VIP: <b>{vip_level['name']}</b>\n\n"
        f"📅 <b>Daily Rakeback</b>\n"
        f"  Rate: <b>{vip_level['cashback_pct']}%</b> of daily wager\n"
        f"  Available: <b>{daily_amount:,.4f} Tokens</b>\n"
        f"  Status: {'✅ Claimable' if can_daily and daily_amount > 0 else '⏳ Already claimed today' if not can_daily else '❌ No wager today'}\n\n"
        f"📆 <b>Weekly Rakeback</b>\n"
        f"  Rate: <b>{rakeback_rate}%</b> of weekly wager\n"
        f"  Available: <b>{weekly_amount:,.4f} Tokens</b>\n"
        f"  Status: {'✅ Claimable' if can_weekly and weekly_amount > 0 else '⏳ Come back in 7 days' if not can_weekly else '❌ No wager this week'}\n"
        f"{SEP}"
    )
