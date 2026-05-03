"""
Promo Code System
Admin creates promo codes with:
- bonus percent on deposit
- min/max deposit amount
- expiry hours
- max activations
- broadcast to all users
"""
import json
import uuid
from datetime import datetime, timedelta
from database import db
from utils.logger import logger


async def create_promo(
    code: str,
    bonus_pct: float,
    min_deposit: float,
    max_deposit: float,
    expiry_hours: int,
    max_uses: int,
    min_withdraw: float = 0.0
) -> dict:
    promo = {
        "code": code.upper(),
        "bonus_pct": bonus_pct,
        "min_deposit": min_deposit,
        "max_deposit": max_deposit,
        "min_withdraw": min_withdraw,
        "expires_at": (datetime.utcnow() + timedelta(hours=expiry_hours)).isoformat(),
        "max_uses": max_uses,
        "used_by": [],
        "active": True,
    }
    all_promos = await get_all_promos()
    all_promos[code.upper()] = promo
    await db.set_setting("promo_codes", json.dumps(all_promos))
    return promo


async def get_all_promos() -> dict:
    raw = await db.get_setting("promo_codes")
    if raw:
        return json.loads(raw)
    return {}


async def get_promo(code: str) -> dict | None:
    all_promos = await get_all_promos()
    return all_promos.get(code.upper())


async def validate_promo(code: str, user_id: int, deposit_amount: float) -> tuple[bool, str, float]:
    """Returns (valid, message, bonus_amount)"""
    promo = await get_promo(code)
    if not promo:
        return False, "❌ Invalid promo code!", 0

    if not promo.get("active"):
        return False, "❌ Promo code is no longer active!", 0

    # Check expiry
    expires = datetime.fromisoformat(promo["expires_at"])
    if datetime.utcnow() > expires:
        return False, "❌ Promo code has expired!", 0

    # Check max uses
    if len(promo["used_by"]) >= promo["max_uses"]:
        return False, "❌ Promo code has reached max activations!", 0

    # Check already used
    if user_id in promo["used_by"]:
        return False, "❌ You have already used this promo code!", 0

    # Check min/max deposit
    if deposit_amount < promo["min_deposit"]:
        return False, f"❌ Minimum deposit for this promo is {promo['min_deposit']:,.2f} Tokens!", 0

    if deposit_amount > promo["max_deposit"]:
        return False, f"❌ Maximum deposit for this promo is {promo['max_deposit']:,.2f} Tokens!", 0

    bonus = round(deposit_amount * promo["bonus_pct"] / 100, 4)
    return True, f"✅ Promo applied! +{promo['bonus_pct']}% bonus = +{bonus:,.4f} Tokens!", bonus


async def use_promo(code: str, user_id: int):
    """Mark promo as used by user."""
    all_promos = await get_all_promos()
    promo = all_promos.get(code.upper())
    if promo and user_id not in promo["used_by"]:
        promo["used_by"].append(user_id)
        all_promos[code.upper()] = promo
        await db.set_setting("promo_codes", json.dumps(all_promos))


async def deactivate_promo(code: str):
    all_promos = await get_all_promos()
    if code.upper() in all_promos:
        all_promos[code.upper()]["active"] = False
        await db.set_setting("promo_codes", json.dumps(all_promos))


def promo_info_text(promo: dict) -> str:
    from ui.messages import SEP
    expires = datetime.fromisoformat(promo["expires_at"])
    remaining = max(0, (expires - datetime.utcnow()).seconds // 3600)
    uses_left = promo["max_uses"] - len(promo["used_by"])
    return (
        f"🎁 <b>PROMO CODE ACTIVE!</b>\n{SEP}\n"
        f"Code: <code>{promo['code']}</code>\n"
        f"Bonus: <b>+{promo['bonus_pct']}%</b> on deposit\n"
        f"Min deposit: <b>{promo['min_deposit']:,.2f}</b> Tokens\n"
        f"Max deposit: <b>{promo['max_deposit']:,.2f}</b> Tokens\n"
        f"⏰ Expires in: <b>{remaining}h</b>\n"
        f"🔢 Activations left: <b>{uses_left}</b>"
    )


async def get_user_promo_min_withdraw(user_id: int) -> float:
    """Get minimum withdrawal amount for user based on their used promo."""
    raw = await db.get_setting(f"used_promo_{user_id}")
    if not raw:
        return 0.0
    promo = await get_promo(raw)
    if not promo:
        return 0.0
    return float(promo.get("min_withdraw", 0.0))
