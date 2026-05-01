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
        f"📈 Pick your <b>target multiplier</b>.\n"
        f"The rocket launches — if it flies past your target, <b>YOU WIN!</b>\n\n"
        f"⚡ Higher multiplier = bigger win, higher risk!\n\n"
        f"🎯 Choose multiplier:",
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
        # ── Decide result FIRST so animation matches reality ──────────
        won = random.random() * 100 < win_percent

        if won:
            crash = round(random.uniform(multiplier, multiplier * 3), 2)
        else:
            if multiplier > 2:
                crash = round(random.uniform(1.0, multiplier - 0.01), 2)
            else:
                crash = round(random.uniform(1.0, 1.99), 2)

        # ── Build animation steps up to actual crash value only ───────
        steps = []
        if crash > 1.5:
            steps.append(round(1.0 + (crash - 1.0) * 0.35, 2))
        if crash > 2.5:
            steps.append(round(1.0 + (crash - 1.0) * 0.70, 2))

        def _frame(current: float, label: str) -> str:
            bar_filled = min(int((current / max(crash * 1.1, 2.0)) * 16), 16)
            bar = "█" * bar_filled + "░" * (16 - bar_filled)
            return (
                f"🚀 <b>LIMBO</b> — Target: <b>{multiplier}x</b>\n{SEP}\n"
                f"┌─────────────────┐\n"
                f"│  {current:.2f}x  🚀\n"
                f"│ [{bar}]\n"
                f"└─────────────────┘\n"
                f"<i>{label}</i>"
            )

        anim_labels = ["Launching rocket...", "Rising fast...", "Climbing higher..."]

        try:
            msg = await callback.message.edit_text(_frame(1.00, anim_labels[0]), parse_mode="HTML")
        except:
            msg = await callback.message.answer(_frame(1.00, anim_labels[0]), parse_mode="HTML")

        for i, step in enumerate(steps):
            await asyncio.sleep(0.8)
            try:
                await msg.edit_text(_frame(step, anim_labels[i + 1]), parse_mode="HTML")
            except:
                pass

        await asyncio.sleep(0.8)

        # ── Final frame shows only actual crash point ─────────────────
        bar_filled = min(int((crash / (multiplier * 2)) * 16), 16)
        bar = "█" * bar_filled + "░" * (16 - bar_filled)
        crash_line = f"💥 <b>{crash}x</b>" if not won else f"🎯 <b>{crash}x</b> ✅"

        final_frame = (
            f"🚀 <b>LIMBO</b> — Target: <b>{multiplier}x</b>\n{SEP}\n"
            f"┌──────────────────┐\n"
            f"│ [{bar}] │\n"
            f"│  Crashed: {crash_line} │\n"
            f"└──────────────────┘\n"
        )

        await db.unlock_balance(user_id)
        await db.update_wagered(user_id, bet)

        if won:
            gross = round(bet * multiplier, 4)
            tax = round(gross * tax_pct / 100, 4)
            reward = round(gross - tax, 4)
            await db.update_token_balance(user_id, reward - bet)
            await db.add_transaction(user_id, "win", reward, currency="TOKEN")
            result = (
                f"\n🎉 <b>ROCKET REACHED TARGET!</b>\n"
                f"💰 Bet: {bet:,.4f} | Win: {gross:,.4f}\n"
                f"🧾 Tax ({tax_pct}%): -{tax:,.4f}\n"
                f"✅ Net: <b>+{reward:,.4f} Tokens</b>"
            )
        else:
            await db.update_token_balance(user_id, -bet)
            await db.add_transaction(user_id, "loss", bet, currency="TOKEN")
            result = (
                f"\n😢 <b>ROCKET CRASHED EARLY!</b>\n"
                f"💸 Lost: <b>-{bet:,.4f} Tokens</b>"
            )

        user = await db.get_user(user_id)
        try:
            await msg.edit_text(
                final_frame + result + f"\n{SEP}\n🪙 Balance: <b>{user['token_balance']:,.4f}</b>",
                parse_mode="HTML", reply_markup=back_kb("menu_games")
            )
        except:
            await callback.message.answer(
                final_frame + result + f"\n{SEP}\n🪙 Balance: <b>{user['token_balance']:,.4f}</b>",
                parse_mode="HTML", reply_markup=back_kb("menu_games")
            )
        logger.info(f"Limbo | user={user_id} | bet={bet} | mult={multiplier}x | crash={crash}x | won={won}")
    except Exception as e:
        await db.unlock_balance(user_id); raise e
