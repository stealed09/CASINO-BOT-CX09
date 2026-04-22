from aiogram.types import Message
from aiogram import Bot
from database import db
from utils.helpers import calculate_win_reward, calculate_referral_bonus
from ui.messages import game_result_text
from ui.keyboards import back_to_main_kb
from utils.logger import logger
import asyncio
import random


async def play_limbo(message: Message, bot: Bot, bet: float):
    user_id = message.from_user.id

    await db.update_balance(user_id, -bet)
    await db.lock_balance(user_id, bet)
    await db.add_transaction(user_id, "bet", bet)

    target = random.randint(1, 6)
    dice_msg = await bot.send_dice(message.chat.id, emoji="🎲")
    await asyncio.sleep(4)

    value = dice_msg.dice.value
    won = value == target

    await db.unlock_balance(user_id)
    await db.update_wagered(user_id, bet)

    user_data = await db.get_user(user_id)
    if user_data and user_data.get("referral_id"):
        bonus = calculate_referral_bonus(bet)
        if bonus > 0:
            await db.update_referral_earnings(user_data["referral_id"], bonus)
            await db.add_transaction(user_data["referral_id"], "referral", bonus)

    if won:
        reward, tax = calculate_win_reward(bet)
        await db.update_balance(user_id, reward)
        await db.add_transaction(user_id, "win", reward)
        result_emoji = "🚀🎉"
    else:
        reward, tax = 0, 0
        await db.add_transaction(user_id, "loss", bet)
        result_emoji = "🚀😢"

    updated = await db.get_user(user_id)
    text = game_result_text(
        f"Limbo (Target:{target} | Got:{value})", won, bet, reward, tax,
        updated["balance"], result_emoji
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=back_to_main_kb())
    logger.info(f"Limbo | user={user_id} | bet={bet} | target={target} | value={value} | won={won}")
