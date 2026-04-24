"""
Dice game — Easy mode and Crazy mode.
Crazy mode: bot rolls first, then waits for user to physically send a 🎲 dice.
"""
import asyncio
from aiogram.types import Message, CallbackQuery
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import db
from utils.logger import logger
from ui.messages import SEP
from ui.keyboards import back_kb


# Store pending crazy mode sessions: user_id -> {bet, bot_val, chat_id, msg_id}
_crazy_pending: dict = {}


def dice_mode_kb(amount: float) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="😊 Easy Mode", callback_data=f"dice_easy_{amount}"),
        InlineKeyboardButton(text="🔥 Crazy Mode", callback_data=f"dice_crazy_{amount}"),
    )
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="menu_games"))
    return builder.as_markup()


async def play_dice(message: Message, bot: Bot, bet: float):
    await message.answer(
        f"🎲 <b>DICE GAME</b>\n{SEP}\n"
        f"💰 Bet: <b>{bet:,.4f} Tokens</b>\n\n"
        f"<b>😊 Easy Mode:</b> Roll ≥4 = WIN (1.9x)\n"
        f"<b>🔥 Crazy Mode:</b> Bot rolls first, then YOU roll — beat bot = WIN (2x)\n\n"
        f"Choose mode:",
        parse_mode="HTML",
        reply_markup=dice_mode_kb(bet)
    )
    return None


async def play_dice_easy(callback: CallbackQuery, bot: Bot, bet: float):
    user_id = callback.from_user.id
    tax_pct = float(await db.get_setting("game_tax_percent") or "5")
    await db.lock_balance(user_id, bet)
    try:
        try:
            await callback.message.edit_text(f"🎲 Rolling dice...", parse_mode="HTML")
        except: pass
        dice_msg = await bot.send_dice(callback.message.chat.id, emoji="🎲")
        await asyncio.sleep(4)
        value = dice_msg.dice.value
        won = value >= 4
        await db.unlock_balance(user_id)
        await db.update_wagered(user_id, bet)
        if won:
            gross = round(bet * 1.9, 4)
            tax = round(gross * tax_pct / 100, 4)
            reward = round(gross - tax, 4)
            await db.update_token_balance(user_id, reward - bet)
            await db.add_transaction(user_id, "win", reward, currency="TOKEN")
            result = (f"🎲 <b>DICE Easy</b>\n{SEP}\nRolled: <b>{value}</b>\n🎉 <b>WIN!</b>\n"
                      f"Gross: {gross:,.4f} | Tax: -{tax:,.4f}\n✅ +<b>{reward:,.4f} Tokens</b>")
        else:
            await db.update_token_balance(user_id, -bet)
            await db.add_transaction(user_id, "loss", bet, currency="TOKEN")
            result = f"🎲 <b>DICE Easy</b>\n{SEP}\nRolled: <b>{value}</b>\n😢 <b>LOSE!</b>\n💸 -<b>{bet:,.4f} Tokens</b>"
        user = await db.get_user(user_id)
        await callback.message.answer(result + f"\n🪙 Balance: <b>{user['token_balance']:,.4f}</b>",
                                       parse_mode="HTML", reply_markup=back_kb("menu_games"))
    except Exception as e:
        await db.unlock_balance(user_id); raise e


async def play_dice_crazy(callback: CallbackQuery, bot: Bot, bet: float):
    """Bot rolls first, stores result, user must physically send 🎲."""
    user_id = callback.from_user.id
    await db.lock_balance(user_id, bet)
    try:
        try:
            await callback.message.edit_text(
                f"🎲 <b>Crazy Mode</b>\n🤖 Bot rolling first...", parse_mode="HTML"
            )
        except: pass
        bot_dice = await bot.send_dice(callback.message.chat.id, emoji="🎲")
        await asyncio.sleep(4)
        bot_val = bot_dice.dice.value
        # Store pending session
        _crazy_pending[user_id] = {
            "bet": bet,
            "bot_val": bot_val,
            "chat_id": callback.message.chat.id
        }
        await callback.message.answer(
            f"🤖 Bot rolled: <b>{bot_val}</b>\n\n"
            f"🎲 Now <b>YOU</b> roll! Send a 🎲 dice in this chat!\n"
            f"<i>(Tap the emoji button or sticker picker → dice)</i>",
            parse_mode="HTML"
        )
    except Exception as e:
        await db.unlock_balance(user_id); raise e


async def resolve_dice_crazy(user_id: int, user_val: int, bot: Bot):
    """Called when user sends a dice in crazy mode."""
    session = _crazy_pending.pop(user_id, None)
    if not session:
        return False
    bet = session["bet"]
    bot_val = session["bot_val"]
    chat_id = session["chat_id"]
    tax_pct = float(await db.get_setting("game_tax_percent") or "5")
    won = user_val > bot_val
    await db.unlock_balance(user_id)
    await db.update_wagered(user_id, bet)
    if won:
        gross = round(bet * 2.0, 4)
        tax = round(gross * tax_pct / 100, 4)
        reward = round(gross - tax, 4)
        await db.update_token_balance(user_id, reward - bet)
        await db.add_transaction(user_id, "win", reward, currency="TOKEN")
        result = (f"🎲 <b>DICE Crazy</b>\n{SEP}\n🤖 Bot: <b>{bot_val}</b> | You: <b>{user_val}</b>\n"
                  f"🎉 <b>YOU WIN!</b>\nGross: {gross:,.4f} | Tax: -{tax:,.4f}\n✅ +<b>{reward:,.4f} Tokens</b>")
    else:
        await db.update_token_balance(user_id, -bet)
        await db.add_transaction(user_id, "loss", bet, currency="TOKEN")
        result = (f"🎲 <b>DICE Crazy</b>\n{SEP}\n🤖 Bot: <b>{bot_val}</b> | You: <b>{user_val}</b>\n"
                  f"😢 <b>BOT WINS!</b>\n💸 -<b>{bet:,.4f} Tokens</b>")
    user = await db.get_user(user_id)
    from aiogram import Bot as BotClass
    from ui.keyboards import back_kb as _back
    await bot.send_message(chat_id,
        result + f"\n🪙 Balance: <b>{user['token_balance']:,.4f}</b>",
        parse_mode="HTML", reply_markup=_back("menu_games"))
    logger.info(f"Dice Crazy | user={user_id} | bot={bot_val} | user={user_val} | won={won}")
    return True

