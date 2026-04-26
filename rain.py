"""
Rain Drops System
Admin or auto-triggered token rain.
First N users who click "Catch Rain" share the pot.
"""

import asyncio
from typing import Dict, Set, Optional
from datetime import datetime

SEP = "─" * 24

# Active rain: only one at a time
active_rain: Optional[dict] = None


def create_rain(
    amount: float,
    max_winners: int,
    duration_seconds: int = 60,
    triggered_by: str = "Admin",
    rain_type: str = "admin",  # admin | auto | vip
) -> dict:
    global active_rain
    active_rain = {
        "amount": amount,
        "max_winners": max_winners,
        "duration": duration_seconds,
        "triggered_by": triggered_by,
        "rain_type": rain_type,
        "participants": set(),
        "started_at": datetime.now().isoformat(),
        "active": True,
        "share_per_user": 0.0,
    }
    return active_rain


def join_rain(user_id: int) -> Optional[dict]:
    """User joins rain. Returns rain or None if not active/already joined/full."""
    global active_rain
    if not active_rain or not active_rain["active"]:
        return None
    if user_id in active_rain["participants"]:
        return None
    if len(active_rain["participants"]) >= active_rain["max_winners"]:
        return None
    active_rain["participants"].add(user_id)
    return active_rain


def finish_rain() -> Optional[dict]:
    global active_rain
    if not active_rain:
        return None
    rain = active_rain
    rain["active"] = False
    n = len(rain["participants"])
    if n > 0:
        rain["share_per_user"] = round(rain["amount"] / n, 4)
    else:
        rain["share_per_user"] = 0.0
    active_rain = None
    return rain


def rain_announce_text(rain: dict) -> str:
    rain_emojis = {"admin": "🌧️", "auto": "⛈️", "vip": "💎"}
    emoji = rain_emojis.get(rain["rain_type"], "🌧️")
    return (
        f"{emoji} <b>RAIN DROP!</b>\n{SEP}\n"
        f"💰 Total Pool: <b>{rain['amount']:,.4f} Tokens</b>\n"
        f"👥 Max Winners: <b>{rain['max_winners']}</b>\n"
        f"⏳ Ends in: <b>{rain['duration']} seconds</b>\n"
        f"{SEP}\n"
        f"Tap below to catch the rain! 🌧️"
    )


def rain_result_text(rain: dict) -> str:
    n = len(rain["participants"])
    return (
        f"🌧️ <b>RAIN ENDED</b>\n{SEP}\n"
        f"👥 Winners: <b>{n}</b>\n"
        f"💰 Each got: <b>{rain['share_per_user']:,.4f} Tokens</b>\n"
        f"💵 Total distributed: <b>{rain['amount']:,.4f} Tokens</b>"
    )


def get_active_rain() -> Optional[dict]:
    return active_rain
