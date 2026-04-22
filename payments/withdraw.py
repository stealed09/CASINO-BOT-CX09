from aiogram.types import Message, CallbackQuery
from aiogram import Bot
from database import db
from config import ADMIN_IDS
from ui.keyboards import approve_reject_withdraw_kb, back_kb
from ui.messages import success_text, error_text, SEP
from utils.logger import logger


async def process_withdrawal(message: Message, bot: Bot, amount: float, upi_id: str):
    user_id = message.from_user.id

    withdraw_enabled = await db.get_setting("withdraw_enabled")
    if withdraw_enabled != "1":
        await message.answer(
            error_text("Withdrawals are currently disabled. Try later."),
            parse_mode="Markdown",
            reply_markup=back_kb()
        )
        return

    min_wd = float(await db.get_setting("min_withdrawal") or "100")
    user = await db.get_user(user_id)

    if not user:
        await message.answer(error_text("User not found. Please /start."), parse_mode="Markdown")
        return

    if amount < min_wd:
        await message.answer(
            error_text(f"Minimum withdrawal is ₹{min_wd:,.2f}"),
            parse_mode="Markdown",
            reply_markup=back_kb()
        )
        return

    if user["balance"] < amount:
        await message.answer(
            error_text(f"Insufficient balance.\nYour balance: ₹{user['balance']:,.2f}"),
            parse_mode="Markdown",
            reply_markup=back_kb()
        )
        return

    # Deduct immediately and hold
    await db.update_balance(user_id, -amount)
    wid = await db.create_withdrawal(user_id, amount, upi_id)
    await db.add_transaction(user_id, "withdraw", amount, "pending")

    uname = user.get("username", str(user_id))

    await message.answer(
        success_text(
            f"Withdrawal request submitted!\n"
            f"💰 Amount: ₹{amount:,.2f}\n"
            f"🏦 UPI: {upi_id}\n"
            f"🆔 Request ID: #{wid}\n\n"
            f"⏳ Processing within 24 hours."
        ),
        parse_mode="Markdown",
        reply_markup=back_kb()
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"💸 *WITHDRAWAL REQUEST*\n{SEP}\n"
                f"👤 User: @{uname} (`{user_id}`)\n"
                f"💰 Amount: *₹{amount:,.2f}*\n"
                f"🏦 UPI: `{upi_id}`\n"
                f"🆔 Withdrawal ID: *#{wid}*",
                parse_mode="Markdown",
                reply_markup=approve_reject_withdraw_kb(wid)
            )
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")


async def approve_withdrawal(callback: CallbackQuery, bot: Bot, wid: int):
    wd = await db.get_withdrawal(wid)
    if not wd:
        await callback.answer("Not found!", show_alert=True)
        return
    if wd["status"] != "pending":
        await callback.answer("Already processed!", show_alert=True)
        return

    await db.update_withdrawal_status(wid, "paid")
    await callback.message.edit_text(
        f"✅ *WITHDRAWAL PAID*\n{SEP}\n"
        f"🆔 ID: #{wid}\n"
        f"💰 Amount: ₹{wd['amount']:,.2f}\n"
        f"🏦 UPI: {wd['upi_id']}",
        parse_mode="Markdown"
    )

    try:
        await bot.send_message(
            wd["user_id"],
            success_text(
                f"Your withdrawal of ₹{wd['amount']:,.2f} has been paid!\n"
                f"🏦 To UPI: {wd['upi_id']}"
            ),
            parse_mode="Markdown",
            reply_markup=back_kb()
        )
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")

    await callback.answer("✅ Withdrawal marked as paid!")


async def reject_withdrawal(callback: CallbackQuery, bot: Bot, wid: int):
    wd = await db.get_withdrawal(wid)
    if not wd:
        await callback.answer("Not found!", show_alert=True)
        return
    if wd["status"] != "pending":
        await callback.answer("Already processed!", show_alert=True)
        return

    # Refund
    await db.update_balance(wd["user_id"], wd["amount"])
    await db.update_withdrawal_status(wid, "rejected")
    await db.add_transaction(wd["user_id"], "deposit", wd["amount"], "refund")

    await callback.message.edit_text(
        f"❌ *WITHDRAWAL REJECTED & REFUNDED*\n{SEP}\nID: #{wid}",
        parse_mode="Markdown"
    )

    try:
        await bot.send_message(
            wd["user_id"],
            error_text(
                f"Your withdrawal #{wid} was rejected.\n"
                f"₹{wd['amount']:,.2f} has been refunded to your balance."
            ),
            parse_mode="Markdown",
            reply_markup=back_kb()
        )
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")

    await callback.answer("❌ Rejected & refunded!")
