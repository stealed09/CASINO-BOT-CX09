"""
Slot Machine 🎰
Classic 3-reel slots with symbols, multipliers, jackpot pool.
"""

import random
from typing import List, Tuple

SEP = "─" * 24

SYMBOLS = [
    {"sym": "🍒", "name": "Cherry",  "weight": 35, "mult": 2.0},
    {"sym": "🍋", "name": "Lemon",   "weight": 25, "mult": 3.0},
    {"sym": "🍊", "name": "Orange",  "weight": 20, "mult": 4.0},
    {"sym": "🍇", "name": "Grapes",  "weight": 12, "mult": 6.0},
    {"sym": "🔔", "name": "Bell",    "weight": 5,  "mult": 10.0},
    {"sym": "⭐", "name": "Star",    "weight": 2,  "mult": 25.0},
    {"sym": "💎", "name": "Diamond", "weight": 0.8,"mult": 50.0},
    {"sym": "7️⃣", "name": "Seven",  "weight": 0.2,"mult": 100.0},
]

POPULATION = []
WEIGHTS = []
for s in SYMBOLS:
    POPULATION.append(s["sym"])
    WEIGHTS.append(s["weight"])


def spin_reels() -> List[str]:
    return random.choices(POPULATION, weights=WEIGHTS, k=3)


def get_multiplier(reels: List[str]) -> Tuple[float, str]:
    """Return (multiplier, result_label). 0 = loss."""
    if reels[0] == reels[1] == reels[2]:
        sym = reels[0]
        for s in SYMBOLS:
            if s["sym"] == sym:
                if s["name"] == "Seven":
                    return s["mult"], "🎰 JACKPOT!!!"
                if s["name"] == "Diamond":
                    return s["mult"], "💎 MEGA WIN!"
                return s["mult"], f"🎉 THREE {s['name'].upper()}S!"
    # Two matching
    if reels[0] == reels[1] or reels[1] == reels[2]:
        matching = reels[0] if reels[0] == reels[1] else reels[1]
        for s in SYMBOLS:
            if s["sym"] == matching:
                return round(s["mult"] * 0.3, 2), "✨ Two of a kind!"
    # Cherry anywhere = small win
    if "🍒" in reels:
        return 0.5, "🍒 Cherry bonus!"
    return 0.0, "❌ No match"


def slot_result_text(
    reels: List[str],
    bet: float,
    multiplier: float,
    label: str,
    game_tax: float,
) -> str:
    display = " | ".join(reels)
    if multiplier > 0:
        gross = round(bet * multiplier, 4)
        tax = round(gross * game_tax / 100, 4)
        net = gross - tax
        result = (
            f"{label}\n"
            f"💰 Win: <b>{gross:,.4f}</b>\n"
            f"🏷️ Tax ({game_tax}%): <b>-{tax:,.4f}</b>\n"
            f"✅ Net: <b>+{net:,.4f} Tokens</b>"
        )
    else:
        net = 0.0
        result = f"{label}\n💸 Lost: <b>{bet:,.4f} Tokens</b>"

    return (
        f"🎰 <b>SLOT MACHINE</b>\n{SEP}\n"
        f"┌───────────────┐\n"
        f"│  {display}  │\n"
        f"└───────────────┘\n"
        f"💵 Bet: <b>{bet:,.4f} Tokens</b>\n"
        f"{result}"
    ), net


def slots_help_text() -> str:
    lines = [f"🎰 <b>SLOT PAYTABLE</b>\n{SEP}"]
    lines.append("<b>Three of a kind:</b>")
    for s in SYMBOLS:
        lines.append(f"{s['sym']}{s['sym']}{s['sym']} → <b>{s['mult']}x</b>")
    lines.append("\n<b>Two of a kind:</b> 0.3x of symbol value")
    lines.append("🍒 Cherry anywhere → <b>0.5x</b>")
    return "\n".join(lines)
