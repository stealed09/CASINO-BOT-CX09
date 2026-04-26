"""
PVP Duel System
User vs User games — Dice Duel, Coinflip Duel, High Roll
House takes a small fee from winnings.
"""

import asyncio
import random
from typing import Dict, Optional
from datetime import datetime

SEP = "─" * 24

# Active duels: duel_id → duel state
active_duels: Dict[str, dict] = {}


def create_duel(
    creator_id: int,
    creator_name: str,
    game_type: str,  # "dice" | "coinflip" | "highroll"
    bet: float,
    house_fee_pct: float = 5.0,
) -> str:
    """Create a new duel. Returns duel_id."""
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
        "status": "waiting",  # waiting | active | finished
        "created_at": datetime.now().isoformat(),
        "result": None,
        "winner_id": None,
    }
    return duel_id


def join_duel(duel_id: str, opponent_id: int, opponent_name: str) -> Optional[dict]:
    """Opponent joins a duel. Returns duel or None if not found/invalid."""
    duel = active_duels.get(duel_id)
    if not duel:
        return None
    if duel["status"] != "waiting":
        return None
    if duel["creator_id"] == opponent_id:
        return None
    duel["opponent_id"] = opponent_id
    duel["opponent_name"] = opponent_name
    duel["status"] = "active"
    return duel


def resolve_duel(duel_id: str) -> Optional[dict]:
    """Resolve duel, determine winner. Returns updated duel."""
    duel = active_duels.get(duel_id)
    if not duel or duel["status"] != "active":
        return None

    game = duel["game_type"]
    bet = duel["bet"]
    fee_pct = duel["house_fee_pct"]
    prize_pool = bet * 2
    house_fee = round(prize_pool * fee_pct / 100, 4)
    net_prize = round(prize_pool - house_fee, 4)

    if game == "dice":
        c_roll = random.randint(1, 6)
        o_roll = random.randint(1, 6)
        while c_roll == o_roll:  # reroll on tie
            o_roll = random.randint(1, 6)
        winner = duel["creator_id"] if c_roll > o_roll else duel["opponent_id"]
        duel["result"] = {
            "creator_roll": c_roll,
            "opponent_roll": o_roll,
        }

    elif game == "coinflip":
        flip = random.choice(["heads", "tails"])
        # Creator always gets heads
        winner = duel["creator_id"] if flip == "heads" else duel["opponent_id"]
        duel["result"] = {"flip": flip}

    elif game == "highroll":
        c_roll = random.randint(1, 100)
        o_roll = random.randint(1, 100)
        while c_roll == o_roll:
            o_roll = random.randint(1, 100)
        winner = duel["creator_id"] if c_roll > o_roll else duel["opponent_id"]
        duel["result"] = {
            "creator_roll": c_roll,
            "opponent_roll": o_roll,
        }
    else:
        return None

    duel["winner_id"] = winner
    duel["net_prize"] = net_prize
    duel["house_fee"] = house_fee
    duel["status"] = "finished"
    return duel


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
            f"🎲 {creator}: <b>{result['creator_roll']}</b>\n"
            f"🎲 {opponent}: <b>{result['opponent_roll']}</b>"
        )
    else:
        detail = ""

    return (
        f"⚔️ <b>PVP DUEL RESULT</b>\n{SEP}\n"
        f"{detail}\n\n"
        f"🏆 Winner: <b>{winner_name}</b>\n"
        f"💰 Prize: <b>{net:,.4f} Tokens</b>\n"
        f"🏠 House Fee ({duel['house_fee_pct']}%): <b>{fee:,.4f}</b>\n"
        f"💵 Each bet: <b>{bet:,.4f} Tokens</b>"
    )


def duel_waiting_text(duel: dict) -> str:
    game_names = {"dice": "🎲 Dice Duel", "coinflip": "🪙 Coinflip Duel", "highroll": "🎯 High Roll"}
    return (
        f"⚔️ <b>PVP DUEL CREATED</b>\n{SEP}\n"
        f"Game: <b>{game_names.get(duel['game_type'], duel['game_type'])}</b>\n"
        f"Creator: <b>{duel['creator_name']}</b>\n"
        f"💵 Bet: <b>{duel['bet']:,.4f} Tokens</b>\n"
        f"{SEP}\n"
        f"To join: <code>/joinduel {duel['id']}</code>\n"
        f"⏳ Expires in 5 minutes"
    )


def get_open_duels() -> list:
    """Return all waiting duels."""
    return [d for d in active_duels.values() if d["status"] == "waiting"]


def cancel_duel(duel_id: str, user_id: int) -> bool:
    """Cancel a duel if creator requests it."""
    duel = active_duels.get(duel_id)
    if not duel:
        return False
    if duel["creator_id"] != user_id:
        return False
    if duel["status"] != "waiting":
        return False
    duel["status"] = "cancelled"
    active_duels.pop(duel_id, None)
    return True


async def auto_expire_duel(duel_id: str, timeout: int = 300):
    """Cancel duel after timeout seconds if still waiting."""
    await asyncio.sleep(timeout)
    duel = active_duels.get(duel_id)
    if duel and duel["status"] == "waiting":
        active_duels.pop(duel_id, None)
