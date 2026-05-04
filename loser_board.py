"""
Loser Leaderboard
- Real losers mixed with fake international names (NO Indian names)
- Refreshes every 1 HOUR (not seconds)
- Admin controls: max entries (3-4), max fake bet amount
"""
import random
from datetime import datetime
from typing import List, Dict

SEP = "─" * 24

# Only international names — NO Indian names
INTERNATIONAL_NAMES = [
    "Alex_JP", "Maria_BR", "Chen_CN", "Ivan_RU", "Ahmed_AE", "Sophie_FR",
    "Carlos_MX", "Yuki_JP", "Hassan_EG", "Emma_DE", "Luca_IT",
    "James_UK", "Ana_ES", "Kim_KR", "Zara_ZA", "Max_AU", "Nina_SE",
    "Omar_SA", "Lucia_AR", "Taro_JP", "Anya_RU", "Diego_CO", "Mia_NL",
    "Kevin_US", "Lisa_CA", "Felix_NG", "Marco_IT", "Elena_GR", "Sam_NZ",
    "Yuna_KR", "Pavel_CZ", "Rosa_PH", "Jake_CA", "Hana_JP", "Leo_DE",
    "Sara_SE", "Tom_AU", "Amy_UK", "Bob_US", "Chloe_FR", "Dan_NZ",
    "Eva_IT", "Frank_BR", "Grace_KR", "Hugo_ES", "Iris_CN", "Jack_ZA",
]


def _fake_name() -> str:
    return random.choice(INTERNATIONAL_NAMES)


def _fake_loss(max_amount: float = 50000) -> float:
    return round(random.uniform(max_amount * 0.01, max_amount), 2)


def generate_loser_board(real_losers: List[Dict], count: int = 4, max_fake_amount: float = 50000) -> List[Dict]:
    entries = []

    # Add real losers
    for r in real_losers[:count]:
        name = r.get("username") or str(r.get("user_id", "Player"))
        entries.append({
            "name": str(name)[:12],
            "amount": round(float(r.get("total_lost", 0)), 2),
            "real": True,
        })

    # Fill with fake entries up to count
    needed = count - len(entries)
    used_names = {e["name"] for e in entries}
    for _ in range(needed):
        name = _fake_name()
        while name in used_names:
            name = _fake_name()
        used_names.add(name)
        entries.append({
            "name": name,
            "amount": _fake_loss(max_fake_amount),
            "real": False,
        })

    entries.sort(key=lambda x: x["amount"], reverse=True)
    return entries[:count]


def loser_board_text(entries: List[Dict], next_refresh: str = "") -> str:
    lines = [f"💀 <b>LOSER LEADERBOARD</b>\n{SEP}"]
    medals = ["🥇", "🥈", "🥉", "4️⃣"]
    for i, e in enumerate(entries):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        lines.append(f"{medal} <b>{e['name']}</b> — Lost <b>{e['amount']:,.2f} T</b>")
    if next_refresh:
        lines.append(f"\n{SEP}\n<i>⏰ Next refresh: {next_refresh}</i>")
    return "\n".join(lines)
