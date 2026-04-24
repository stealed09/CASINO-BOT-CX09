import asyncio
from aiogram.types import Message
from aiogram import Bot
from database import db
from utils.logger import logger
from ui.messages import SEP
from ui.keyboards import back_kb

WIN_VALUES = {6}


async def play_darts(message: Message, bot: Bot, bet: float):
    user_id = message.from_user.id
    tax_pct = float(await db.get_setting("game_tax_percent") or "5")
    await db.lock_balance(user_id, bet)
    try:
        dice_msg = await bot.send_dice(message.chat.id, emoji="🎯")
        await asyncio.sleep(4)
        value = dice_msg.dice.value
        won = value in WIN_VALUES
        await db.unlock_balance(user_id)
        await db.update_wagered(user_id, bet)
        if won:
            gross = round(bet * 2.5, 4)
            tax = round(gross * tax_pct / 100, 4)
            reward = round(gross - tax, 4)
            await db.update_token_balance(user_id, reward - bet)
            await db.add_transaction(user_id, "win", reward, currency="TOKEN")
            result = (
                f"🎯 <b>DARTS</b>\n{SEP}\nRolled: <b>{value}</b>  🎉 <b>BULLSEYE!</b>\n"
                f"Gross: {gross:,.4f} | Tax: -{tax:,.4f}\n✅ +<b>{reward:,.4f} Tokens</b>"
            )
        else:
            await db.update_token_balance(user_id, -bet)
            await db.add_transaction(user_id, "loss", bet, currency="TOKEN")
            result = (
                f"🎯 <b>DARTS</b>\n{SEP}\nRolled: <b>{value}</b>  😢 <b>MISSED!</b>\n"
                f"💸 -<b>{bet:,.4f} Tokens</b>"
            )
        user = await db.get_user(user_id)
        await message.answer(
            result + f"\n🪙 Balance: <b>{user['token_balance']:,.4f}</b>",
            parse_mode="HTML", reply_markup=back_kb("menu_games")
        )
        logger.info(f"Darts | user={user_id} | bet={bet} | value={value} | won={won}")
        return None
    except Exception as e:
        await db.unlock_balance(user_id); raise e
