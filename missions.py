"""
Complete Mission System - Daily/Weekly/Monthly/Secret
All missions controllable by admin ON/OFF per mission
"""
from typing import List, Dict
from datetime import date, datetime

SEP = "─" * 24

MISSIONS = [
    # DAILY
    {"id":"d_play5","type":"daily","category":"games_played","name":"Play 5 Games","desc":"Play 5 games today","icon":"🎮","target":5,"reward":1,"setting_key":"mission_d_play5"},
    {"id":"d_win3","type":"daily","category":"wins","name":"Win 3 Games","desc":"Win 3 bets today","icon":"🏆","target":3,"reward":2,"setting_key":"mission_d_win3"},
    {"id":"d_wager100","type":"daily","category":"wager","name":"Wager 100","desc":"Wager 100 Tokens today","icon":"💰","target":100,"reward":1,"setting_key":"mission_d_wager100"},
    {"id":"d_wager500","type":"daily","category":"wager","name":"Wager 500","desc":"Wager 500 Tokens today","icon":"💸","target":500,"reward":3,"setting_key":"mission_d_wager500"},
    {"id":"d_limbo2x","type":"daily","category":"limbo_2x","name":"Limbo 2x","desc":"Hit 2x or more on Limbo","icon":"🚀","target":1,"reward":2,"setting_key":"mission_d_limbo2x"},
    {"id":"d_login","type":"daily","category":"login","name":"Daily Login","desc":"Play at least 1 game today","icon":"📅","target":1,"reward":1,"setting_key":"mission_d_login"},
    {"id":"d_deposit","type":"daily","category":"deposit","name":"Deposit Today","desc":"Make a deposit today","icon":"💳","target":1,"reward":5,"setting_key":"mission_d_deposit"},
    # WEEKLY
    {"id":"w_wager15k","type":"weekly","category":"wager","name":"Whale Wager","desc":"Wager 15,000 Tokens this week","icon":"🐋","target":15000,"reward":15,"setting_key":"mission_w_wager15k"},
    {"id":"w_play50","type":"weekly","category":"games_played","name":"Grinder","desc":"Play 50 games this week","icon":"🎰","target":50,"reward":10,"setting_key":"mission_w_play50"},
    {"id":"w_win20","type":"weekly","category":"wins","name":"20 Wins","desc":"Win 20 bets this week","icon":"🥇","target":20,"reward":12,"setting_key":"mission_w_win20"},
    {"id":"w_refer1","type":"weekly","category":"refer","name":"Refer 1","desc":"Refer 1 user who deposits 120+ Tokens","icon":"🤝","target":1,"reward":25,"setting_key":"mission_w_refer1"},
    {"id":"w_streak15","type":"weekly","category":"login_streak","name":"15 Day Streak","desc":"Login 15 days in a row","icon":"🔥","target":15,"reward":15,"setting_key":"mission_w_streak15"},
    # MONTHLY
    {"id":"m_wager50k","type":"monthly","category":"wager","name":"50K Wager","desc":"Wager 50,000 Tokens this month","icon":"💎","target":50000,"reward":50,"setting_key":"mission_m_wager50k"},
    {"id":"m_wager100k","type":"monthly","category":"wager","name":"100K Wager","desc":"Wager 100,000 Tokens this month","icon":"👑","target":100000,"reward":100,"setting_key":"mission_m_wager100k"},
    {"id":"m_refer5","type":"monthly","category":"refer","name":"Refer 5","desc":"Refer 5 users this month","icon":"🌐","target":5,"reward":75,"setting_key":"mission_m_refer5"},
    {"id":"m_vipup","type":"monthly","category":"vip_rankup","name":"VIP Rank Up","desc":"Reach a new VIP level this month","icon":"⬆️","target":1,"reward":50,"setting_key":"mission_m_vipup"},
    # SECRET
    {"id":"s_777","type":"secret","category":"limbo_777","name":"Lucky 7.77","desc":"Hit 7.77x on Limbo","icon":"🍀","target":1,"reward":7,"setting_key":"mission_s_777"},
    {"id":"s_winstreak5","type":"secret","category":"win_streak","name":"5 Win Streak","desc":"Win 5 bets in a row","icon":"⚡","target":5,"reward":10,"setting_key":"mission_s_winstreak5"},
    {"id":"s_comeback","type":"secret","category":"comeback","name":"Comeback","desc":"Win after losing 5 in a row","icon":"💪","target":1,"reward":12,"setting_key":"mission_s_comeback"},
]

MISSION_BY_ID = {m["id"]: m for m in MISSIONS}

TYPE_LABELS = {"daily":"📅 Daily","weekly":"📆 Weekly","monthly":"🗓️ Monthly","secret":"🔐 Secret"}

def get_period_key(mission_type: str) -> str:
    today = date.today()
    if mission_type == "daily":
        return today.isoformat()
    elif mission_type == "weekly":
        week = today.isocalendar()[1]
        return f"{today.year}-W{week}"
    elif mission_type == "monthly":
        return f"{today.year}-{today.month}"
    return "all"

def get_mission_progress_value(mission: dict, progress: dict) -> int:
    return min(int(progress.get(mission["category"], 0)), mission["target"])

def is_complete(mission: dict, progress: dict) -> bool:
    return get_mission_progress_value(mission, progress) >= mission["target"]

def missions_text(progress: dict, claimed_ids: List[str], enabled_ids: List[str]) -> str:
    lines = [f"📋 <b>MISSIONS</b>\n{SEP}"]
    for mtype in ["daily","weekly","monthly","secret"]:
        group = [m for m in MISSIONS if m["type"] == mtype and m["id"] in enabled_ids]
        if not group:
            continue
        lines.append(f"\n{TYPE_LABELS[mtype]}")
        for m in group:
            prog = get_mission_progress_value(m, progress)
            done = is_complete(m, progress)
            claimed = m["id"] in claimed_ids
            if claimed:
                status = "✅ Claimed"
            elif done:
                status = "🎁 Ready to claim!"
            else:
                bar_filled = int((prog / m["target"]) * 5)
                bar = "▓" * bar_filled + "░" * (5 - bar_filled)
                status = f"{bar} {prog}/{m['target']}"
            lines.append(f"{m['icon']} <b>{m['name']}</b> — {m['reward']} T\n   {m['desc']} | {status}")
    return "\n".join(lines)

def claimable_missions(progress: dict, claimed_ids: List[str], enabled_ids: List[str]) -> List[dict]:
    return [m for m in MISSIONS if m["id"] in enabled_ids and is_complete(m, progress) and m["id"] not in claimed_ids]

def get_all_setting_keys() -> List[str]:
    return [m["setting_key"] for m in MISSIONS]
