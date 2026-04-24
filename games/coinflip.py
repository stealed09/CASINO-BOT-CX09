from aiogram.types import Message, CallbackQuery
from aiogram import Bot
from database import db
from utils.helpers import calculate_win_reward, calculate_referral_bonus
from ui.messages import game_result_text
from ui.keyboards import back_to_main_kb, coinflip_choice_kb
from utils.logger import logger
import asyncio
import random


async def prompt_coinflip(message: Message, bet: float):
    await message.answer(
        f"🪙 *COIN FLIP*\n─────────────────────────────\n"
        f"💰 Bet: *₹{bet:,.2f}*\n\n"
        f"Choose your side:",
        parse_mode="Markdown",
        reply_markup=coinflip_choice_kb(str(bet))
    )


async def play_coinflip(callback: CallbackQuery, bot: Bot, bet: float, choice: str):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)

    if not user or user["balance"] < bet:
        await callback.answer("❌ Insufficient balance!", show_alert=True)
        return

    if await db.is_balance_locked(user_id):
        await callback.answer("⏳ Game in progress!", show_alert=True)
        return

    await db.update_balance(user_id, -bet)
    await db.lock_balance(user_id, bet)
    await db.add_transaction(user_id, "bet", bet)

    result = random.choice(["heads", "tails"])
    won = result == choice

    await asyncio.sleep(1)
    await db.unlock_balance(user_id)
    await db.update_wagered(user_id, bet)

    user_data = await db.get_user(user_id)
    if user_data and user_data.get("referral_id"):
        bonus = calculate_referral_bonus(bet)
        if bonus > 0:
            await db.update_referral_earnings(user_data["referral_id"], bonus)
            await db.add_transaction(user_data["referral_id"], "referral", bonus)

    if won:
        _tax_pct = float(await db.get_setting("game_tax_percent") or "5")
        reward, tax = calculate_win_reward(bet, _tax_pct)
        await db.update_balance(user_id, reward)
        await db.add_transaction(user_id, "win", reward)
        result_emoji = "🪙🎉"
    else:
        reward, tax = 0, 0
        await db.add_transaction(user_id, "loss", bet)
        result_emoji = "🪙😢"

    updated = await db.get_user(user_id)
    coin_emoji = "👑" if result == "heads" else "🦅"
    text = game_result_text(
        f"Coin Flip ({coin_emoji} {result.capitalize()})", won, bet, reward, tax,
        updated["balance"], result_emoji
    )
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=back_to_main_kb())
    logger.info(f"CoinFlip | user={user_id} | bet={bet} | choice={choice} | result={result} | won={won}")
