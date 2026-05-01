"""
Lootbox / Cases System
Users open cases for random rewards.

ADMIN CONTROL: All case configs (price, rewards, weights) are stored
in the database. Admin can edit from panel without touching code.
Falls back to DEFAULT_CASES if nothing set in DB yet.
"""

import random
from typing import Dict, List, Tuple

SEP = "─" * 24

DEFAULT_CASES = {
    "common": {
        "name": "Common Case",
        "icon": "📦",
        "price": 100,
        "color": "grey",
        "rewards": [
            {"type": "tokens", "amount": 50,   "label": "50 Tokens",    "weight": 50},
            {"type": "tokens", "amount": 100,  "label": "100 Tokens",   "weight": 30},
            {"type": "tokens", "amount": 200,  "label": "200 Tokens",   "weight": 15},
            {"type": "tokens", "amount": 500,  "label": "500 Tokens",   "weight": 4},
            {"type": "tokens", "amount": 1000, "label": "1,000 Tokens", "weight": 1},
        ]
    },
    "rare": {
        "name": "Rare Case",
        "icon": "💠",
        "price": 500,
        "color": "blue",
        "rewards": [
            {"type": "tokens", "amount": 300,   "label": "300 Tokens",    "weight": 40},
            {"type": "tokens", "amount": 600,   "label": "600 Tokens",    "weight": 30},
            {"type": "tokens", "amount": 1500,  "label": "1,500 Tokens",  "weight": 20},
            {"type": "tokens", "amount": 3000,  "label": "3,000 Tokens",  "weight": 8},
            {"type": "bonus",  "amount": 2.0,   "label": "2x Bonus Mult", "weight": 1.5},
            {"type": "tokens", "amount": 10000, "label": "10,000 Tokens", "weight": 0.5},
        ]
    },
    "epic": {
        "name": "Epic Case",
        "icon": "💜",
        "price": 2000,
        "color": "purple",
        "rewards": [
            {"type": "tokens", "amount": 1000,  "label": "1,000 Tokens",      "weight": 35},
            {"type": "tokens", "amount": 3000,  "label": "3,000 Tokens",      "weight": 30},
            {"type": "tokens", "amount": 7500,  "label": "7,500 Tokens",      "weight": 20},
            {"type": "tokens", "amount": 20000, "label": "20,000 Tokens",     "weight": 10},
            {"type": "vip",    "amount": 1,     "label": "VIP Boost (1 lvl)", "weight": 3},
            {"type": "tokens", "amount": 50000, "label": "50,000 Tokens",     "weight": 2},
        ]
    },
    "legendary": {
        "name": "Legendary Case",
        "icon": "🌟",
        "price": 10000,
        "color": "gold",
        "rewards": [
            {"type": "tokens", "amount": 5000,   "label": "5,000 Tokens",     "weight": 30},
            {"type": "tokens", "amount": 15000,  "label": "15,000 Tokens",    "weight": 25},
            {"type": "tokens", "amount": 50000,  "label": "50,000 Tokens",    "weight": 20},
            {"type": "tokens", "amount": 100000, "label": "100,000 Tokens",   "weight": 15},
            {"type": "vip",    "amount": 2,      "label": "VIP Boost (2 lvl)","weight": 7},
            {"type": "tokens", "amount": 500000, "label": "JACKPOT 500K!",    "weight": 3},
        ]
    }
}

OPENING_ANIMATION = ["📦", "📦✨", "✨📦✨", "🌟✨🌟", "🎉🎊🎉"]

# Runtime cache — loaded from DB on first use
_cases_cache: Dict = {}

# Backward-compat: keep CASES so old imports still work
CASES = DEFAULT_CASES


async def get_cases() -> Dict:
    """Return live case config from DB, else DEFAULT_CASES."""
    global _cases_cache
    try:
        import json
        from database import db
        raw = await db.get_setting("lootbox_cases_config")
        if raw:
            _cases_cache = json.loads(raw)
            return _cases_cache
    except Exception:
        pass
    _cases_cache = {k: dict(v) for k, v in DEFAULT_CASES.items()}
    return _cases_cache


async def save_cases(cases: Dict) -> None:
    """Persist case config to DB and update cache."""
    global _cases_cache, CASES
    import json
    from database import db
    _cases_cache = cases
    CASES = cases
    await db.set_setting("lootbox_cases_config", json.dumps(cases))


def get_cases_sync() -> Dict:
    """Sync accessor for keyboards (can't be async)."""
    return _cases_cache if _cases_cache else DEFAULT_CASES


def open_case(case_key: str) -> Tuple[dict, dict]:
    """Open a case using live cache. Returns (case_info, reward)."""
    cases = get_cases_sync()
    case = cases[case_key]
    rewards = case["rewards"]
    weights = [r["weight"] for r in rewards]
    reward = random.choices(rewards, weights=weights, k=1)[0]
    return case, reward


def cases_menu_text() -> str:
    cases = get_cases_sync()
    lines = [f"📦 <b>LOOTBOXES</b>\n{SEP}"]
    for key, case in cases.items():
        lines.append(
            f"{case['icon']} <b>{case['name']}</b>\n"
            f"  Price: <b>{case['price']:,} Tokens</b>"
        )
    return "\n\n".join(lines)


def case_open_text(case: dict, reward: dict) -> str:
    icon = "🎉" if reward["type"] == "tokens" and reward["amount"] >= 50000 else case["icon"]
    return (
        f"{icon} <b>{case['name']} OPENED!</b>\n{SEP}\n"
        f"🎁 You won: <b>{reward['label']}</b>\n"
    )


def get_case(case_key: str) -> dict:
    return get_cases_sync().get(case_key)


# ── Admin panel helpers ───────────────────────────────────────────────────────

def admin_lootbox_overview_text(cases: Dict) -> str:
    lines = [f"📦 <b>LOOTBOX ADMIN</b>\n{SEP}"]
    for key, case in cases.items():
        rewards_summary = " | ".join(
            f"{r['label']} (w:{r['weight']})" for r in case["rewards"]
        )
        lines.append(
            f"{case['icon']} <b>{case['name']}</b> — {case['price']:,} T\n"
            f"<i>{rewards_summary}</i>"
        )
    lines.append(f"\n{SEP}\nTap a case to edit:")
    return "\n\n".join(lines)


def admin_case_detail_text(case_key: str, case: dict) -> str:
    lines = [
        f"{case['icon']} <b>{case['name']}</b>\n{SEP}",
        f"💰 Price: <b>{case['price']:,} Tokens</b>\n",
        "🎁 <b>Rewards (label | amount | weight):</b>"
    ]
    for i, r in enumerate(case["rewards"]):
        lines.append(f"  {i+1}. {r['label']} | {r['amount']} | weight: {r['weight']}")
    lines.append(f"\n{SEP}\nUse buttons below to edit price or rewards.")
    return "\n".join(lines)
