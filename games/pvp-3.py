"""
PVP Duel System - Complete Rewrite
- Works in groups AND private
- Dice: 1-min loading bar in group, then both roll physically (whoever rolls first shown first)
- Coinflip/Highroll: instant resolve with emoji
- Group notifications with JOIN button
- Auto-expire 5 min if no opponent, 30 sec roll timeout
"""

import asyncio
import random
from typing import Dict, Optional
from datetime import datetime

SEP = "─" * 24

active_duels: Dict[str, dict] = {}

GAME_NAMES = {"dice": "🎲 Dice Duel", "coinflip": "🪙 Coinflip Duel", "highroll": "🎯 High Roll"}
GAME_EMOJIS = {"dice": "🎲", "coinflip": "🪙", "highroll": "🎯"}


def create_duel(creator_id: int, creator_name: str, game_type: str,
                bet: float, house_fee_pct: float = 5.0, chat_id: int = None) -> str:
    duel_id = f"{creator_id}_{int(datetime.now().timestamp())}"
    active_duels[duel_id] = {
        "id": duel_id,
        "creator_id": creator_id,
        "creator_name": creator_name,
        "opponent_id": None,
        "opponent_name": None,
        "game_type": game_type,
        "bet": bet,
        "house_fee_pct": house_fee_pct,
        "status": "waiting",
        "chat_id": chat_id,
        "created_at": datetime.now().isoformat(),
        "winner_id": None,
        "result": None,
        "net_prize": 0.0,
        "house_fee": 0.0,
        "creator_roll": None,
        "opponent_roll": None,
        "rolls_shown": [],  # track who already shown
    }
    return duel_id


def join_duel(duel_id: str, opponent_id: int, opponent_name: str) -> Optional[dict]:
    duel = active_duels.get(duel_id)
    if not duel or duel["status"] != "waiting":
        return None
    if duel["creator_id"] == opponent_id:
        return None
    duel["opponent_id"] = opponent_id
    duel["opponent_name"] = opponent_name
    duel["status"] = "active"
    return duel


def resolve_duel(duel_id: str, creator_roll: int = None, opponent_roll: int = None) -> Optional[dict]:
    duel = active_duels.get(duel_id)
    if not duel or duel["status"] != "active":
        return None
    game = duel["game_type"]
    bet = duel["bet"]
    house_fee = round(bet * 2 * duel["house_fee_pct"] / 100, 4)
    net_prize = round(bet * 2 - house_fee, 4)

    if game == "dice":
        c = creator_roll or duel.get("creator_roll") or random.randint(1, 6)
        o = opponent_roll or duel.get("opponent_roll") or random.randint(1, 6)
        while c == o:
            o = random.randint(1, 6)
        winner = duel["creator_id"] if c > o else duel["opponent_id"]
        duel["result"] = {"creator_roll": c, "opponent_roll": o}
    elif game == "coinflip":
        flip = random.choice(["heads", "tails"])
        winner = duel["creator_id"] if flip == "heads" else duel["opponent_id"]
        duel["result"] = {"flip": flip, "emoji": "👑" if flip == "heads" else "🦅"}
    elif game == "highroll":
        c = random.randint(1, 100)
        o = random.randint(1, 100)
        while c == o:
            o = random.randint(1, 100)
        winner = duel["creator_id"] if c > o else duel["opponent_id"]
        duel["result"] = {"creator_roll": c, "opponent_roll": o}
    else:
        return None

    duel["winner_id"] = winner
    duel["net_prize"] = net_prize
    duel["house_fee"] = house_fee
    duel["status"] = "finished"
    active_duels.pop(duel_id, None)
    return duel


def set_dice_roll(duel_id: str, user_id: int, roll: int) -> Optional[dict]:
    """Store dice roll. Returns duel dict if both rolled."""
    duel = active_duels.get(duel_id)
    if not duel or duel["status"] != "active" or duel["game_type"] != "dice":
        return None
    if duel["creator_id"] == user_id and duel["creator_roll"] is None:
        duel["creator_roll"] = roll
    elif duel["opponent_id"] == user_id and duel["opponent_roll"] is None:
        duel["opponent_roll"] = roll
    else:
        return None
    if duel["creator_roll"] and duel["opponent_roll"]:
        return duel
    return None


def get_pending_duel_for_user(user_id: int) -> Optional[dict]:
    for duel in active_duels.values():
        if duel["status"] != "active" or duel["game_type"] != "dice":
            continue
        if duel["creator_id"] == user_id and duel["creator_roll"] is None:
            return duel
        if duel["opponent_id"] == user_id and duel["opponent_roll"] is None:
            return duel
    return None


def get_open_duels() -> list:
    return [d for d in active_duels.values() if d["status"] == "waiting"]


def cancel_duel(duel_id: str, user_id: int) -> bool:
    duel = active_duels.get(duel_id)
    if not duel or duel["creator_id"] != user_id or duel["status"] != "waiting":
        return False
    active_duels.pop(duel_id, None)
    return True


async def auto_expire_duel(duel_id: str, timeout: int = 300):
    await asyncio.sleep(timeout)
    duel = active_duels.get(duel_id)
    if duel and duel["status"] == "waiting":
        active_duels.pop(duel_id, None)


async def auto_expire_roll(duel_id: str, timeout: int = 30) -> Optional[dict]:
    await asyncio.sleep(timeout)
    return active_duels.get(duel_id)


def duel_waiting_text(duel: dict) -> str:
    game = GAME_NAMES.get(duel["game_type"], duel["game_type"])
    emoji = GAME_EMOJIS.get(duel["game_type"], "⚔️")
    return (
        f"⚔️ <b>PVP DUEL OPEN!</b>\n{SEP}\n"
        f"{emoji} Game: <b>{game}</b>\n"
        f"👤 Creator: <b>{duel['creator_name']}</b>\n"
        f"💵 Bet: <b>{duel['bet']:,.4f} Tokens</b>\n"
        f"{SEP}\n"
        f"⏳ Expires in 5 minutes\n"
        f"👇 Tap JOIN to accept!"
    )


def duel_result_text(duel: dict) -> str:
    game = duel["game_type"]
    result = duel["result"]
    creator = duel["creator_name"]
    opponent = duel["opponent_name"]
    winner_id = duel["winner_id"]
    winner_name = creator if winner_id == duel["creator_id"] else opponent
    loser_name = opponent if winner_id == duel["creator_id"] else creator
    net = duel.get("net_prize", duel["bet"] * 2)
    fee = duel.get("house_fee", 0)

    if game == "dice":
        c_roll = result["creator_roll"]
        o_roll = result["opponent_roll"]
        detail = (
            f"🎲 {creator}: <b>{c_roll}</b>\n"
            f"🎲 {opponent}: <b>{o_roll}</b>"
        )
    elif game == "coinflip":
        flip = result["flip"]
        emoji = result.get("emoji", "🪙")
        detail = (
            f"🪙 Result: <b>{flip.upper()}</b> {emoji}\n"
            f"👑 {creator} = Heads | 🦅 {opponent} = Tails"
        )
    elif game == "highroll":
        detail = (
            f"🎯 {creator}: <b>{result['creator_roll']}</b>\n"
            f"🎯 {opponent}: <b>{result['opponent_roll']}</b>"
        )
    else:
        detail = ""

    return (
        f"⚔️ <b>DUEL RESULT!</b>\n{SEP}\n"
        f"{detail}\n\n"
        f"🏆 Winner: <b>{winner_name}</b>\n"
        f"💀 Loser: <b>{loser_name}</b>\n"
        f"💰 Prize: <b>{net:,.4f} Tokens</b>\n"
        f"🏠 House Fee: <b>{fee:,.4f}</b>"
    )
