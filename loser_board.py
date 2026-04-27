"""
Loser Leaderboard
- Real losers mixed with fake names
- Auto-rotating fake names (Indian 30%, International 70%)
- Refreshes every 10-15 seconds when viewed
- Admin ON/OFF control
"""
import random
from datetime import datetime
from typing import List, Dict

SEP = "─" * 24

INDIAN_NAMES = [
    "Raj_K","Priya_S","Amit_V","Sneha_R","Vikram_P","Pooja_M",
    "Arjun_T","Divya_N","Rohit_G","Neha_C","Karan_B","Riya_D",
    "Suresh_J","Kavya_L","Manish_F","Anita_H","Deepak_W","Sunita_X",
]

INTERNATIONAL_NAMES = [
    "Alex_JP","Maria_BR","Chen_CN","Ivan_RU","Ahmed_AE","Sophie_FR",
    "Carlos_MX","Yuki_JP","Hassan_EG","Emma_DE","Luca_IT","Fatima_PK",
    "James_UK","Ana_ES","Kim_KR","Zara_ZA","Max_AU","Nina_SE",
    "Omar_SA","Lucia_AR","Taro_JP","Anya_RU","Diego_CO","Mia_NL",
    "Raj_SG","Preethi_LK","Kevin_US","Lisa_CA","Felix_NG","Aisha_BD",
    "Marco_IT","Elena_GR","Sam_NZ","Yuna_KR","Pavel_CZ","Rosa_PH",
]


def _fake_name() -> str:
    """30% Indian, 70% International."""
    if random.random() < 0.30:
        return random.choice(INDIAN_NAMES)
    return random.choice(INTERNATIONAL_NAMES)


def _fake_loss() -> float:
    """Random loss amount."""
    return round(random.uniform(200, 50000), 2)


def generate_loser_board(real_losers: List[Dict], count: int = 10) -> List[Dict]:
    """
    Mix real losers with fake entries.
    real_losers: list of {username, total_lost}
    Returns sorted list of top losers.
    """
    entries = []

    # Add real losers (anonymized slightly)
    for r in real_losers[:5]:
        name = r.get("username") or r.get("user_id", "Player")
        entries.append({
            "name": str(name)[:12],
            "amount": round(float(r.get("total_lost", 0)), 2),
            "real": True,
        })

    # Fill rest with fake
    needed = max(count - len(entries), count // 2)
    for _ in range(needed):
        entries.append({
            "name": _fake_name(),
            "amount": _fake_loss(),
            "real": False,
        })

    # Sort by amount descending
    entries.sort(key=lambda x: x["amount"], reverse=True)
    return entries[:count]


def loser_board_text(entries: List[Dict]) -> str:
    lines = [f"💀 <b>LOSER LEADERBOARD</b>\n{SEP}"]
    medals = ["🥇", "🥈", "🥉"]
    for i, e in enumerate(entries):
        medal = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{medal} <b>{e['name']}</b> — Lost {e['amount']:,.2f} T")
    lines.append(f"\n{SEP}\n<i>Updates every few seconds</i>")
    return "\n".join(lines)
