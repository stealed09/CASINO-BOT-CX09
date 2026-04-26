"""
Daily Missions / Quests
Users complete tasks daily for token rewards.
Missions reset at midnight.
"""

from typing import List, Dict
from datetime import date

SEP = "─" * 24

MISSIONS = [
    {
        "id": "wager_500",
        "name": "High Roller",
        "desc": "Wager 500 Tokens today",
        "icon": "💰",
        "target": 500,
        "type": "wager",
        "reward": 50,
    },
    {
        "id": "play_5",
        "name": "Gambler",
        "desc": "Play 5 games today",
        "icon": "🎮",
        "target": 5,
        "type": "games_played",
        "reward": 30,
    },
    {
        "id": "win_3",
        "name": "Lucky Streak",
        "desc": "Win 3 bets today",
        "icon": "🏆",
        "target": 3,
        "type": "wins",
        "reward": 75,
    },
    {
        "id": "wager_2000",
        "name": "Whale Mode",
        "desc": "Wager 2000 Tokens today",
        "icon": "🐋",
        "target": 2000,
        "type": "wager",
        "reward": 200,
    },
    {
        "id": "play_crash",
        "name": "Crash Pilot",
        "desc": "Play Crash game 3 times",
        "icon": "🚀",
        "target": 3,
        "type": "crash_plays",
        "reward": 60,
    },
]


def get_mission_progress(mission: dict, user_progress: dict) -> int:
    return min(user_progress.get(mission["type"], 0), mission["target"])


def is_mission_complete(mission: dict, user_progress: dict) -> bool:
    return get_mission_progress(mission, user_progress) >= mission["target"]


def missions_text(user_progress: dict, claimed_ids: List[str]) -> str:
    today = date.today().isoformat()
    lines = [f"📋 <b>DAILY MISSIONS</b>\n{SEP}\n🗓️ Resets at midnight\n{SEP}"]
    for m in MISSIONS:
        prog = get_mission_progress(m, user_progress)
        done = is_mission_complete(m, user_progress)
        claimed = m["id"] in claimed_ids
        bar_filled = int((prog / m["target"]) * 5)
        bar = "▓" * bar_filled + "░" * (5 - bar_filled)
        status = "✅ CLAIMED" if claimed else ("🎁 Claim!" if done else f"{bar} {prog}/{m['target']}")
        lines.append(
            f"{m['icon']} <b>{m['name']}</b>\n"
            f"  {m['desc']}\n"
            f"  Reward: <b>{m['reward']} Tokens</b> | {status}"
        )
    return "\n\n".join(lines)


def claimable_missions(user_progress: dict, claimed_ids: List[str]) -> List[dict]:
    return [
        m for m in MISSIONS
        if is_mission_complete(m, user_progress) and m["id"] not in claimed_ids
    ]
