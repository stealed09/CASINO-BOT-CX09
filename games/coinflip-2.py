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

# emoji → choice mapping (used in main.py to read user's sent emoji)
COIN_EMOJI = {
    "👑": "heads",
    "🦅": "tails",
}


def coinflip_pick_kb(bet: float) -> InlineKeyboardMarkup:
    """Inline keyboard: pick Heads or Tails."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👑 Heads", callback_data=f"cf_pick_heads_{bet}"),
        InlineKeyboardButton(text="🦅 Tails", callback_data=f"cf_pick_tails_{bet}"),
    )
    builder.row(InlineKeyboardButton(text="❌ Cancel", callback_data="menu_games"))
    return builder.as_markup()


async def prompt_coinflip(message: Message, bet: float):
    """Step 1 — show Heads / Tails inline buttons."""
    await message.answer(
        f"🪙 <b>COIN FLIP</b>\n{SEP}\n"
        f"💰 Bet: <b>{bet:,.4f} Tokens</b>\n\n"
        f"Win = 1.9x your bet\n\n"
        f"Choose your side:",
        parse_mode="HTML",
        reply_markup=coinflip_pick_kb(bet)
    )


async def play_coinflip(message: Message, bot: Bot, bet: float, choice: str):
    """Step 3 — flip coin and show result."""
    user_id = message.from_user.id
    tax_pct = float(await db.get_setting("game_tax_percent") or "5")

    await db.lock_balance(user_id, bet)
    try:
        msg = await message.answer(
            f"🪙 <b>COIN FLIP</b>\n{SEP}\n🌀 Flipping...\n\n🪙 · · ·",
            parse_mode="HTML"
        )
        await asyncio.sleep(0.6)
        try:
            await msg.edit_text(
                f"🪙 <b>COIN FLIP</b>\n{SEP}\n🌀 Flipping...\n\n· 🪙 · ·",
                parse_mode="HTML"
            )
        except:
            pass
        await asyncio.sleep(0.6)

        result = random.choice(["heads", "tails"])
        won = result == choice

        await db.unlock_balance(user_id)
        await db.update_wagered(user_id, bet)

        coin_emoji   = "👑" if result == "heads" else "🦅"
        choice_emoji = "👑" if choice == "heads" else "🦅"

        if won:
            gross  = round(bet * 1.9, 4)
            tax    = round(gross * tax_pct / 100, 4)
            reward = round(gross - tax, 4)
            await db.update_token_balance(user_id, reward - bet)
            await db.add_transaction(user_id, "win", reward, currency="TOKEN")
            result_text = (
                f"🪙 <b>COIN FLIP</b>\n{SEP}\n"
                f"You picked: {choice_emoji} | Result: {coin_emoji} <b>{'Heads' if result == 'heads' else 'Tails'}</b>\n"
                f"🎉 <b>WIN!</b>\n"
                f"Gross: {gross:,.4f} | Tax: -{tax:,.4f}\n"
                f"✅ +<b>{reward:,.4f} Tokens</b>"
            )
        else:
            await db.update_token_balance(user_id, -bet)
            await db.add_transaction(user_id, "loss", bet, currency="TOKEN")
            result_text = (
                f"🪙 <b>COIN FLIP</b>\n{SEP}\n"
                f"You picked: {choice_emoji} | Result: {coin_emoji} <b>{'Heads' if result == 'heads' else 'Tails'}</b>\n"
                f"😢 <b>LOSE!</b>\n💸 -<b>{bet:,.4f} Tokens</b>"
            )

        user = await db.get_user(user_id)
        try:
            await msg.edit_text(
                result_text + f"\n🪙 Balance: <b>{user['token_balance']:,.4f}</b>",
                parse_mode="HTML", reply_markup=back_kb("menu_games")
            )
        except:
            await message.answer(
                result_text + f"\n🪙 Balance: <b>{user['token_balance']:,.4f}</b>",
                parse_mode="HTML", reply_markup=back_kb("menu_games")
            )

        logger.info(f"CoinFlip | user={user_id} | bet={bet} | choice={choice} | result={result} | won={won}")
        return None

    except Exception as e:
        await db.unlock_balance(user_id)
        raise e
