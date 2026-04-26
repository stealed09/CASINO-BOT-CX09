"""
Crash Game
- Multiplier rises from 1.00x
- User must cashout before CRASH
- Telegram message edited live to show rising multiplier
- Auto cashout supported
- Provably fair
"""

import asyncio
import random
from typing import Dict, Optional
from provably_fair import generate_result, result_to_crash, get_or_create_seed_pair, increment_nonce, hash_server_seed

SEP = "─" * 24

# Active crash games: user_id → game state dict
active_crash_games: Dict[int, dict] = {}


def generate_crash_point(server_seed: str, client_seed: str, nonce: int) -> float:
    result = generate_result(server_seed, client_seed, nonce)
    return result_to_crash(result)


def crash_chart(current_mult: float, crashed: bool = False) -> str:
    """Visual multiplier chart using text blocks."""
    if crashed:
        return f"💥 CRASHED @ <b>{current_mult:.2f}x</b>"
    bar_len = min(int((current_mult - 1.0) * 5), 20)
    bar = "█" * bar_len
    return f"📈 {bar} <b>{current_mult:.2f}x</b>"


def crash_message(
    bet: float,
    current_mult: float,
    auto_cashout: Optional[float],
    crashed: bool = False,
    cashed_out: bool = False,
    cashout_mult: Optional[float] = None,
    server_seed_hash: str = "",
) -> str:
    status = ""
    if cashed_out and cashout_mult:
        win = round(bet * cashout_mult, 4)
        status = f"\n✅ <b>CASHED OUT @ {cashout_mult:.2f}x</b>\n💰 Won: <b>{win:,.4f} Tokens</b>"
    elif crashed:
        status = f"\n💥 <b>CRASHED! You lost {bet:,.4f} Tokens</b>"
    else:
        current_val = round(bet * current_mult, 4)
        status = f"\n💰 Current Value: <b>{current_val:,.4f} Tokens</b>"
        if auto_cashout:
            status += f"\n⚡ Auto cashout at: <b>{auto_cashout:.2f}x</b>"

    return (
        f"🚀 <b>CRASH GAME</b>\n{SEP}\n"
        f"💵 Bet: <b>{bet:,.4f} Tokens</b>\n"
        f"{crash_chart(current_mult, crashed)}"
        f"{status}\n"
        f"{SEP}\n"
        f"🔐 Hash: <code>{server_seed_hash[:16]}...</code>"
    )


async def run_crash_game(
    bot,
    user_id: int,
    chat_id: int,
    message_id: int,
    bet: float,
    auto_cashout: Optional[float],
    crash_point: float,
    server_seed_hash: str,
    db,
    game_tax: float,
):
    """
    Core crash game loop. Edits the message every tick.
    Runs until crash_point reached or user cashouts.
    """
    from aiogram.exceptions import TelegramBadRequest

    current_mult = 1.00
    tick = 0
    cashed_out = False
    cashout_mult = None

    active_crash_games[user_id] = {
        "running": True,
        "cashed_out": False,
        "current_mult": 1.00,
        "bet": bet,
        "crash_point": crash_point,
    }

    try:
        while current_mult < crash_point:
            if not active_crash_games.get(user_id, {}).get("running", False):
                break

            # Check if user manually cashed out
            if active_crash_games[user_id].get("cashed_out", False):
                cashout_mult = active_crash_games[user_id].get("cashout_mult", current_mult)
                cashed_out = True
                break

            # Auto cashout
            if auto_cashout and current_mult >= auto_cashout:
                cashout_mult = current_mult
                cashed_out = True
                break

            # Update multiplier — grows faster as it rises
            tick += 1
            speed = 0.03 + (current_mult - 1.0) * 0.01
            current_mult = round(current_mult + speed, 2)
            active_crash_games[user_id]["current_mult"] = current_mult

            # Edit message every 2 ticks to avoid flood limits
            if tick % 2 == 0:
                try:
                    await bot.edit_message_text(
                        crash_message(bet, current_mult, auto_cashout,
                                      server_seed_hash=server_seed_hash),
                        chat_id=chat_id,
                        message_id=message_id,
                        parse_mode="HTML"
                    )
                except TelegramBadRequest:
                    pass

            await asyncio.sleep(0.5)

        # Final state
        if cashed_out and cashout_mult:
            win = round(bet * cashout_mult, 4)
            tax = round(win * game_tax / 100, 4)
            net = win - tax
            await db.update_token_balance(user_id, net)
            await db.add_transaction(user_id, "crash_win", net, "completed", "TOKEN")
            final_msg = crash_message(
                bet, cashout_mult, auto_cashout,
                cashed_out=True, cashout_mult=cashout_mult,
                server_seed_hash=server_seed_hash
            )
            if tax > 0:
                final_msg += f"\n🏷️ Tax ({game_tax}%): <b>-{tax:,.4f}</b>\n✅ Net: <b>+{net:,.4f} Tokens</b>"
        else:
            # Crashed
            current_mult = crash_point
            await db.add_transaction(user_id, "crash_loss", bet, "completed", "TOKEN")
            final_msg = crash_message(
                bet, crash_point, auto_cashout,
                crashed=True,
                server_seed_hash=server_seed_hash
            )

        from ui.keyboards import back_to_main_kb
        try:
            await bot.edit_message_text(
                final_msg,
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML",
                reply_markup=back_to_main_kb()
            )
        except TelegramBadRequest:
            await bot.send_message(chat_id, final_msg, parse_mode="HTML",
                                   reply_markup=back_to_main_kb())

    finally:
        active_crash_games.pop(user_id, None)


async def cashout_crash(user_id: int) -> Optional[float]:
    """Called when user sends /cashout. Returns mult or None if no game."""
    game = active_crash_games.get(user_id)
    if not game or not game.get("running"):
        return None
    mult = game["current_mult"]
    game["cashed_out"] = True
    game["cashout_mult"] = mult
    return mult
