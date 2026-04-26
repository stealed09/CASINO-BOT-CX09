"""
Lootbox / Cases System
Users open cases for random rewards.
"""

import random
from typing import Dict, List, Tuple

SEP = "─" * 24

CASES = {
    "common": {
        "name": "Common Case",
        "icon": "📦",
        "price": 100,
        "color": "grey",
        "rewards": [
            {"type": "tokens", "amount": 50,   "label": "50 Tokens",        "weight": 50},
            {"type": "tokens", "amount": 100,  "label": "100 Tokens",       "weight": 30},
            {"type": "tokens", "amount": 200,  "label": "200 Tokens",       "weight": 15},
            {"type": "tokens", "amount": 500,  "label": "500 Tokens",       "weight": 4},
            {"type": "tokens", "amount": 1000, "label": "1,000 Tokens",     "weight": 1},
        ]
    },
    "rare": {
        "name": "Rare Case",
        "icon": "💠",
        "price": 500,
        "color": "blue",
        "rewards": [
            {"type": "tokens", "amount": 300,   "label": "300 Tokens",      "weight": 40},
            {"type": "tokens", "amount": 600,   "label": "600 Tokens",      "weight": 30},
            {"type": "tokens", "amount": 1500,  "label": "1,500 Tokens",    "weight": 20},
            {"type": "tokens", "amount": 3000,  "label": "3,000 Tokens",    "weight": 8},
            {"type": "bonus",  "amount": 2.0,   "label": "2x Bonus Mult",   "weight": 1.5},
            {"type": "tokens", "amount": 10000, "label": "10,000 Tokens",   "weight": 0.5},
        ]
    },
    "epic": {
        "name": "Epic Case",
        "icon": "💜",
        "price": 2000,
        "color": "purple",
        "rewards": [
            {"type": "tokens", "amount": 1000,  "label": "1,000 Tokens",    "weight": 35},
            {"type": "tokens", "amount": 3000,  "label": "3,000 Tokens",    "weight": 30},
            {"type": "tokens", "amount": 7500,  "label": "7,500 Tokens",    "weight": 20},
            {"type": "tokens", "amount": 20000, "label": "20,000 Tokens",   "weight": 10},
            {"type": "vip",    "amount": 1,     "label": "VIP Boost (1 lvl)","weight": 3},
            {"type": "tokens", "amount": 50000, "label": "50,000 Tokens",   "weight": 2},
        ]
    },
    "legendary": {
        "name": "Legendary Case",
        "icon": "🌟",
        "price": 10000,
        "color": "gold",
        "rewards": [
            {"type": "tokens", "amount": 5000,   "label": "5,000 Tokens",   "weight": 30},
            {"type": "tokens", "amount": 15000,  "label": "15,000 Tokens",  "weight": 25},
            {"type": "tokens", "amount": 50000,  "label": "50,000 Tokens",  "weight": 20},
            {"type": "tokens", "amount": 100000, "label": "100,000 Tokens", "weight": 15},
            {"type": "vip",    "amount": 2,      "label": "VIP Boost (2 lvl)","weight": 7},
            {"type": "tokens", "amount": 500000, "label": "JACKPOT 500K!",  "weight": 3},
        ]
    }
}

OPENING_ANIMATION = ["📦", "📦✨", "✨📦✨", "🌟✨🌟", "🎉🎊🎉"]


def open_case(case_key: str) -> Tuple[dict, dict]:
    """Open a case. Returns (case_info, reward)."""
    case = CASES[case_key]
    rewards = case["rewards"]
    weights = [r["weight"] for r in rewards]
    reward = random.choices(rewards, weights=weights, k=1)[0]
    return case, reward


def cases_menu_text() -> str:
    lines = [f"📦 <b>LOOTBOXES</b>\n{SEP}"]
    for key, case in CASES.items():
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
    return CASES.get(case_key)
