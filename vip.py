"""
VIP / Level System
Levels based on lifetime wagered amount.
Admin can customize thresholds and perks via settings.
"""

from typing import Dict, Optional

# ── VIP Level Definitions ──────────────────────────────────────────────────────

VIP_LEVELS = [
    {
        "level": 0,
        "name": "Bronze",
        "badge": "🥉",
        "min_wager": 0,
        "withdraw_tax_discount": 0.0,   # % discount on withdraw tax
        "cashback_pct": 0.0,            # daily rakeback %
        "weekly_bonus_multiplier": 1.0,
        "color": "bronze",
    },
    {
        "level": 1,
        "name": "Silver",
        "badge": "🥈",
        "min_wager": 10_000,
        "withdraw_tax_discount": 1.0,
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
        "cashback_pct": 2.0,
        "weekly_bonus_multiplier": 2.0,
        "color": "diamond",
    },
]


def get_vip_level(total_wagered: float) -> Dict:
    """Return the VIP level dict for a given total_wagered."""
    current = VIP_LEVELS[0]
    for lvl in VIP_LEVELS:
        if total_wagered >= lvl["min_wager"]:
            current = lvl
    return current


def get_next_vip_level(total_wagered: float) -> Optional[Dict]:
    """Return next VIP level or None if already max."""
    current = get_vip_level(total_wagered)
    idx = current["level"]
    if idx + 1 < len(VIP_LEVELS):
        return VIP_LEVELS[idx + 1]
    return None


def vip_progress_bar(total_wagered: float) -> str:
    """Return a text progress bar toward next VIP level."""
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
    """Return VIP info block for user profile."""
    wagered = user.get("total_wagered", 0)
    lvl = get_vip_level(wagered)
    nxt = get_next_vip_level(wagered)
    bar = vip_progress_bar(wagered)

    text = (
        f"{lvl['badge']} <b>VIP: {lvl['name']}</b>\n"
        f"📊 Progress: {bar}\n"
        f"⚡ Rakeback: <b>{lvl['cashback_pct']}%</b> daily\n"
        f"🎁 Bonus Multiplier: <b>{lvl['weekly_bonus_multiplier']}x</b>\n"
        f"💸 Tax Discount: <b>{lvl['withdraw_tax_discount']}%</b>\n"
    )
    if nxt:
        remaining = nxt["min_wager"] - wagered
        text += f"\n🔜 Next: {nxt['badge']} {nxt['name']} — Need <b>{remaining:,.0f}</b> more wager"
    else:
        text += "\n🏆 <b>You are at the highest VIP level!</b>"
    return text


def vip_levels_info_text() -> str:
    """Return text showing all VIP levels and requirements."""
    lines = ["💎 <b>VIP LEVELS</b>\n"]
    for lvl in VIP_LEVELS:
        lines.append(
            f"{lvl['badge']} <b>{lvl['name']}</b>\n"
            f"  • Wager Required: <b>{lvl['min_wager']:,.0f}</b> Tokens\n"
            f"  • Rakeback: <b>{lvl['cashback_pct']}%</b>\n"
            f"  • Bonus: <b>{lvl['weekly_bonus_multiplier']}x</b>\n"
            f"  • Tax Discount: <b>{lvl['withdraw_tax_discount']}%</b>\n"
        )
    return "\n".join(lines)
