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


def coinflip_pick_kb(bet: float) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👑 Heads", callback_data=f"cf_pick_heads_{bet}"),
        InlineKeyboardButton(text="🦅 Tails", callback_data=f"cf_pick_tails_{bet}"),
    )
    builder.row(InlineKeyboardButton(text="❌ Cancel", callback_data="menu_games"))
    return builder.as_markup()


async def prompt_coinflip(message: Message, bet: float):
    """Step 1 — show Heads/Tails inline buttons."""
    await message.answer(
        f"🪙 <b>COIN FLIP</b>\n{SEP}\n"
        f"💰 Bet: <b>{bet:,.4f} Tokens</b>\n\n"
        f"Win = 1.9x your bet\n\n"
        f"Pick your side:",
        parse_mode="HTML",
        reply_markup=coinflip_pick_kb(bet)
    )


async def coinflip_side_selected(callback: CallbackQuery, bot: Bot, bet: float, choice: str):
    """Step 2 — animate coin in chat, show result."""
    user_id = callback.from_user.id
    tax_pct = float(await db.get_setting("game_tax_percent") or "5")
    choice_label = "Heads 👑" if choice == "heads" else "Tails 🦅"

    await db.lock_balance(user_id, bet)
    try:
        # Show flipping state
        await callback.message.edit_text(
            f"🪙 <b>COIN FLIP</b>\n{SEP}\n"
            f"💰 Bet: <b>{bet:,.4f} Tokens</b>\n"
            f"Your pick: <b>{choice_label}</b>\n\n"
            f"🌀 Flipping...",
            parse_mode="HTML"
        )

        # Use 🎲 dice — 1,2,3 = tails / 4,5,6 = heads
        # Send it in chat so user sees animation
        dice_msg = await bot.send_dice(chat_id=user_id, emoji="🎲")
        dice_val = dice_msg.dice.value
        result = "heads" if dice_val >= 4 else "tails"
        won = result == choice

        # Wait for dice animation (~3s)
        await asyncio.sleep(3)

        await db.unlock_balance(user_id)
        await db.update_wagered(user_id, bet)

        coin_result = "Heads 👑" if result == "heads" else "Tails 🦅"

        if won:
            gross  = round(bet * 1.9, 4)
            tax    = round(gross * tax_pct / 100, 4)
            reward = round(gross - tax, 4)
            await db.update_token_balance(user_id, reward - bet)
            await db.add_transaction(user_id, "win", reward, currency="TOKEN")
            result_text = (
                f"🪙 <b>COIN FLIP</b>\n{SEP}\n"
                f"Your pick: <b>{choice_label}</b>\n"
                f"Result: <b>{coin_result}</b>\n\n"
                f"🎉 <b>WIN!</b>\n"
                f"Gross: {gross:,.4f} | Tax: -{tax:,.4f}\n"
                f"✅ +<b>{reward:,.4f} Tokens</b>"
            )
        else:
            await db.update_token_balance(user_id, -bet)
            await db.add_transaction(user_id, "loss", bet, currency="TOKEN")
            result_text = (
                f"🪙 <b>COIN FLIP</b>\n{SEP}\n"
                f"Your pick: <b>{choice_label}</b>\n"
                f"Result: <b>{coin_result}</b>\n\n"
                f"😢 <b>LOSE!</b>\n"
                f"💸 -<b>{bet:,.4f} Tokens</b>"
            )

        user = await db.get_user(user_id)
        await bot.send_message(
            chat_id=user_id,
            text=result_text + f"\n{SEP}\n🪙 Balance: <b>{user['token_balance']:,.4f}</b>",
            parse_mode="HTML",
            reply_markup=back_kb("menu_games")
        )
        logger.info(f"CoinFlip | user={user_id} | bet={bet} | choice={choice} | result={result} | dice={dice_val} | won={won}")

    except Exception as e:
        await db.unlock_balance(user_id)
        raise e
