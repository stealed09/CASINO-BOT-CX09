"""
Limbo — user picks a multiplier (2x, 3x, 5x, 10x, 25x, 50x, 100x).
Win chance = admin-set win_percent / 100.
Win = bet * multiplier * (1 - tax%).
"""
import asyncio
import random
from aiogram.types import Message, CallbackQuery
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import db
from utils.logger import logger
from ui.messages import SEP
from ui.keyboards import back_kb


MULTIPLIERS = [2, 3, 5, 10, 25, 50, 100]


def limbo_mult_kb(bet: float) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    row = []
    for m in MULTIPLIERS:
        row.append(InlineKeyboardButton(text=f"{m}x", callback_data=f"limbo_mult_{bet}_{m}"))
        if len(row) == 4:
            builder.row(*row); row = []
    if row:
        builder.row(*row)
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="menu_games"))
    return builder.as_markup()


async def play_limbo(message: Message, bot: Bot, bet: float):
    await message.answer(
        f"🚀 <b>LIMBO</b>\n{SEP}\n"
        f"💰 Bet: <b>{bet:,.4f} Tokens</b>\n\n"
        f"Choose your target multiplier.\n"
        f"Higher multiplier = bigger win but lower chance!\n\n"
        f"🎯 Pick multiplier:",
        parse_mode="HTML",
        reply_markup=limbo_mult_kb(bet)
    )
    return None


async def play_limbo_multiplier(callback: CallbackQuery, bot: Bot, bet: float, multiplier: int):
    user_id = callback.from_user.id
    tax_pct = float(await db.get_setting("game_tax_percent") or "5")
    win_percent = float(await db.get_setting("limbo_win_percent") or "20")

    await db.lock_balance(user_id, bet)
    try:
        try:
            await callback.message.edit_text(
                f"🚀 <b>LIMBO</b> — Target: <b>{multiplier}x</b>\n{SEP}\nLaunching...",
                parse_mode="HTML"
            )
        except: pass

        await asyncio.sleep(2)

        # Admin-controlled win %
        won = random.random() * 100 < win_percent

        # Generate a "crash point" for display
        if won:
            # Crash at or above multiplier
            crash = round(random.uniform(multiplier, multiplier * 3), 2)
        else:
            # Crash below multiplier
            if multiplier > 2:
                crash = round(random.uniform(1.0, multiplier - 0.01), 2)
            else:
                crash = round(random.uniform(1.0, 1.99), 2)

        await db.unlock_balance(user_id)
        await db.update_wagered(user_id, bet)

        if won:
            gross = round(bet * multiplier, 4)
            tax = round(gross * tax_pct / 100, 4)
            reward = round(gross - tax, 4)
            await db.update_token_balance(user_id, reward - bet)
            await db.add_transaction(user_id, "win", reward, currency="TOKEN")
            result = (
                f"🚀 <b>LIMBO</b>\n{SEP}\n"
                f"🎯 Target: <b>{multiplier}x</b> | 💥 Crashed: <b>{crash}x</b>\n"
                f"🎉 <b>YOU WIN!</b> Rocket reached your target!\n"
                f"💰 Bet: {bet:,.4f} | Gross: {gross:,.4f}\n"
                f"🧾 Tax ({tax_pct}%): -{tax:,.4f}\n"
                f"✅ Net: <b>+{reward:,.4f} Tokens</b>"
            )
        else:
            await db.update_token_balance(user_id, -bet)
            await db.add_transaction(user_id, "loss", bet, currency="TOKEN")
            result = (
                f"🚀 <b>LIMBO</b>\n{SEP}\n"
                f"🎯 Target: <b>{multiplier}x</b> | 💥 Crashed: <b>{crash}x</b>\n"
                f"😢 <b>CRASHED!</b> Rocket didn't reach your target.\n"
                f"💸 Lost: <b>-{bet:,.4f} Tokens</b>"
            )

        user = await db.get_user(user_id)
        await callback.message.answer(
            result + f"\n{SEP}\n🪙 Balance: <b>{user['token_balance']:,.4f}</b>",
            parse_mode="HTML", reply_markup=back_kb("menu_games")
        )
        logger.info(f"Limbo | user={user_id} | bet={bet} | mult={multiplier}x | crash={crash}x | won={won}")
    except Exception as e:
        await db.unlock_balance(user_id); raise e
