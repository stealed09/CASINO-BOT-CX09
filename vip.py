"""
VIP / Level System
Levels based on lifetime wagered amount.
Admin can customize thresholds and perks via panel.
"""

from typing import Dict, List, Optional

DEFAULT_VIP_LEVELS = [
    {
        "level": 0,
        "name": "Bronze",
        "badge": "🥉",
        "min_wager": 0,
        "withdraw_tax_discount": 0.0,
        "deposit_tax_discount": 0.0,
        "cashback_pct": 0.0,
        "weekly_bonus_multiplier": 1.0,
        "color": "bronze",
    },
    {
        "level": 1,
        "name": "Silver",
        "badge": "🥈",
        "min_wager": 10_000,
        "withdraw_tax_discount": 1.0,
        "deposit_tax_discount": 0.5,
        "cashback_pct": 0.5,
        "weekly_bonus_multiplier": 1.2,
        "color": "silver",
    },
    {
        "level": 2,
        "name": "Gold",
        "badge": "🥇",
        "min_wager": 50_000,
        "withdraw_tax_discount": 2.0,
        "deposit_tax_discount": 1.0,
        "cashback_pct": 1.0,
        "weekly_bonus_multiplier": 1.5,
        "color": "gold",
    },
    {
        "level": 3,
        "name": "Diamond",
        "badge": "💎",
        "min_wager": 200_000,
        "withdraw_tax_discount": 4.0,
        "deposit_tax_discount": 2.0,
        "cashback_pct": 2.0,
        "weekly_bonus_multiplier": 2.0,
        "color": "diamond",
    },
]

_vip_levels_cache: List[Dict] = []

# Backward-compat alias
VIP_LEVELS = DEFAULT_VIP_LEVELS


async def get_vip_levels() -> List[Dict]:
    """Return live VIP levels from DB, else defaults."""
    global _vip_levels_cache
    try:
        import json
        from database import db
        raw = await db.get_setting("vip_levels_config")
        if raw:
            _vip_levels_cache = json.loads(raw)
            return _vip_levels_cache
    except Exception:
        pass
    _vip_levels_cache = [dict(l) for l in DEFAULT_VIP_LEVELS]
    return _vip_levels_cache


async def save_vip_levels(levels: List[Dict]) -> None:
    """Persist VIP levels to DB and update cache."""
    global _vip_levels_cache, VIP_LEVELS
    import json
    from database import db
    _vip_levels_cache = levels
    VIP_LEVELS = levels
    await db.set_setting("vip_levels_config", json.dumps(levels))


def get_vip_levels_sync() -> List[Dict]:
    return _vip_levels_cache if _vip_levels_cache else DEFAULT_VIP_LEVELS


def get_vip_level(total_wagered: float) -> Dict:
    """Return the VIP level dict for a given total_wagered."""
    levels = get_vip_levels_sync()
    current = levels[0]
    for lvl in levels:
        if total_wagered >= lvl["min_wager"]:
            current = lvl
    return current


def get_next_vip_level(total_wagered: float) -> Optional[Dict]:
    """Return next VIP level or None if already max."""
    levels = get_vip_levels_sync()
    current = get_vip_level(total_wagered)
    idx = current["level"]
    if idx + 1 < len(levels):
        return levels[idx + 1]
    return None


def vip_progress_bar(total_wagered: float) -> str:
    current = get_vip_level(total_wagered)
    nxt = get_next_vip_level(total_wagered)
    if not nxt:
        return "▓▓▓▓▓▓▓▓▓▓ MAX"
    progress = total_wagered - current["min_wager"]
    needed = nxt["min_wager"] - current["min_wager"]
    pct = min(progress / needed, 1.0)
    filled = int(pct * 10)
    bar = "▓" * filled + "░" * (10 - filled)
    return f"{bar} {pct*100:.0f}%"


def vip_profile_text(user: Dict) -> str:
    wagered = user.get("total_wagered", 0)
    lvl = get_vip_level(wagered)
    nxt = get_next_vip_level(wagered)
    bar = vip_progress_bar(wagered)

    text = (
        f"{lvl['badge']} <b>VIP: {lvl['name']}</b>\n"
        f"📊 Progress: {bar}\n"
        f"⚡ Rakeback: <b>{lvl['cashback_pct']}%</b> daily\n"
        f"🎁 Bonus Multiplier: <b>{lvl['weekly_bonus_multiplier']}x</b>\n"
        f"💸 Withdraw Tax Discount: <b>{lvl['withdraw_tax_discount']}%</b>\n"
        f"📥 Deposit Tax Discount: <b>{lvl.get('deposit_tax_discount', 0.0)}%</b>\n"
    )
    if nxt:
        remaining = nxt["min_wager"] - wagered
        text += f"\n🔜 Next: {nxt['badge']} {nxt['name']} — Need <b>{remaining:,.0f}</b> more wager"
    else:
        text += "\n🏆 <b>You are at the highest VIP level!</b>"
    return text


def vip_levels_info_text() -> str:
    levels = get_vip_levels_sync()
    lines = ["💎 <b>VIP LEVELS</b>\n"]
    for lvl in levels:
        lines.append(
            f"{lvl['badge']} <b>{lvl['name']}</b>\n"
            f"  • Wager Required: <b>{lvl['min_wager']:,.0f}</b> Tokens\n"
            f"  • Rakeback: <b>{lvl['cashback_pct']}%</b>\n"
            f"  • Bonus: <b>{lvl['weekly_bonus_multiplier']}x</b>\n"
            f"  • Withdraw Tax Discount: <b>{lvl['withdraw_tax_discount']}%</b>\n"
            f"  • Deposit Tax Discount: <b>{lvl.get('deposit_tax_discount', 0.0)}%</b>\n"
        )
    return "\n".join(lines)


# ── Admin helpers ─────────────────────────────────────────────────────────────

def admin_vip_overview_text(levels: List[Dict]) -> str:
    SEP = "─" * 24
    lines = [f"💎 <b>VIP LEVEL ADMIN</b>\n{SEP}"]
    for lvl in levels:
        lines.append(
            f"{lvl['badge']} <b>{lvl['name']}</b> (Level {lvl['level']})\n"
            f"  Min Wager: {lvl['min_wager']:,.0f}\n"
            f"  WD Tax Discount: {lvl['withdraw_tax_discount']}%\n"
            f"  Dep Tax Discount: {lvl.get('deposit_tax_discount', 0.0)}%\n"
            f"  Rakeback: {lvl['cashback_pct']}%\n"
            f"  Bonus Mult: {lvl['weekly_bonus_multiplier']}x"
        )
    lines.append(f"\n{SEP}\nTap a level to edit it:")
    return "\n\n".join(lines)
