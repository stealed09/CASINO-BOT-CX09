"""
PVP Duel System - Full Rewrite
- Works in groups AND private
- Dice duel: players physically roll 🎲 (30 sec timer each)
- Coinflip/Highroll: instant resolve
- Group notifications with JOIN button
- Auto-expire after 5 min if no opponent
"""

import asyncio
import random
from typing import Dict, Optional
from datetime import datetime

SEP = "─" * 24

active_duels: Dict[str, dict] = {}


def create_duel(creator_id: int, creator_name: str, game_type: str,
                bet: float, house_fee_pct: float = 5.0,
                chat_id: int = None) -> str:
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
        "chat_id": chat_id,          # group chat where duel was created
        "created_at": datetime.now().isoformat(),
        "result": None,
        "winner_id": None,
        # dice roll tracking
        "creator_roll": None,
        "opponent_roll": None,
        "creator_rolled_at": None,
        "opponent_rolled_at": None,
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
        c = creator_roll or random.randint(1, 6)
        o = opponent_roll or random.randint(1, 6)
        while c == o:
            o = random.randint(1, 6)
        winner = duel["creator_id"] if c > o else duel["opponent_id"]
        duel["result"] = {"creator_roll": c, "opponent_roll": o}

    elif game == "coinflip":
        flip = random.choice(["heads", "tails"])
        winner = duel["creator_id"] if flip == "heads" else duel["opponent_id"]
        duel["result"] = {"flip": flip}

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
    active_duels.pop(duel["id"], None)
    return duel


def set_dice_roll(duel_id: str, user_id: int, roll: int) -> Optional[dict]:
    """Store dice roll. Returns duel if both players have rolled."""
    duel = active_duels.get(duel_id)
    if not duel or duel["status"] != "active" or duel["game_type"] != "dice":
        return None
    if duel["creator_id"] == user_id and duel["creator_roll"] is None:
        duel["creator_roll"] = roll
        duel["creator_rolled_at"] = datetime.now().isoformat()
    elif duel["opponent_id"] == user_id and duel["opponent_roll"] is None:
        duel["opponent_roll"] = roll
        duel["opponent_rolled_at"] = datetime.now().isoformat()
    # Both rolled?
    if duel["creator_roll"] and duel["opponent_roll"]:
        return duel
    return None


def get_pending_duel_for_user(user_id: int) -> Optional[dict]:
    """Find active dice duel where this user hasn't rolled yet."""
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


async def auto_expire_roll(duel_id: str, user_id: int, timeout: int = 30):
    """Cancel duel if user doesn't roll in time."""
    await asyncio.sleep(timeout)
    duel = active_duels.get(duel_id)
    if not duel or duel["status"] != "active":
        return
    if duel["creator_id"] == user_id and duel["creator_roll"] is None:
        return duel  # signal timeout
    if duel["opponent_id"] == user_id and duel["opponent_roll"] is None:
        return duel
    return None


GAME_NAMES = {
    "dice":     "🎲 Dice Duel",
    "coinflip": "🪙 Coinflip Duel",
    "highroll": "🎯 High Roll",
}

GAME_EMOJIS = {
    "dice":     "🎲",
    "coinflip": "🪙",
    "highroll": "🎯",
}


def duel_waiting_text(duel: dict) -> str:
    game = GAME_NAMES.get(duel["game_type"], duel["game_type"])
    return (
        f"⚔️ <b>PVP DUEL OPEN!</b>\n{SEP}\n"
        f"Game: <b>{game}</b>\n"
        f"Creator: <b>{duel['creator_name']}</b>\n"
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
    bet = duel["bet"]
    net = duel.get("net_prize", bet * 2)
    fee = duel.get("house_fee", 0)

    if game == "dice":
        detail = (
            f"🎲 {creator}: <b>{result['creator_roll']}</b>\n"
            f"🎲 {opponent}: <b>{result['opponent_roll']}</b>"
        )
    elif game == "coinflip":
        flip = result["flip"]
        detail = (
            f"🪙 Flip: <b>{flip.upper()}</b>\n"
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
        f"💰 Prize: <b>{net:,.4f} Tokens</b>\n"
        f"🏠 House Fee: <b>{fee:,.4f}</b>"
    )
