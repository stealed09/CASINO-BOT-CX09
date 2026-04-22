from aiogram.types import Message, CallbackQuery
from aiogram import Bot
from database import db
from config import ADMIN_IDS, STAR_PAYMENT_ID, UPI_ID
from ui.keyboards import approve_reject_deposit_kb, back_kb, paid_confirm_kb
from ui.messages import deposit_stars_text, deposit_upi_text, success_text, error_text, SEP
from utils.logger import logger


async def show_deposit_stars(callback: CallbackQuery):
    await callback.message.edit_text(
        deposit_stars_text(STAR_PAYMENT_ID),
        parse_mode="Markdown",
        reply_markup=back_kb("wallet_deposit")
    )
    await callback.answer()


async def show_deposit_upi(callback: CallbackQuery):
    await callback.message.edit_text(
        deposit_upi_text(UPI_ID),
        parse_mode="Markdown",
        reply_markup=back_kb("wallet_deposit")
    )
    await callback.answer()


async def process_stars_deposit(message: Message, bot: Bot, amount: float):
    user_id = message.from_user.id
    did = await db.create_deposit(user_id, "stars", amount)
    user = await db.get_user(user_id)
    uname = user.get("username", str(user_id)) if user else str(user_id)

    await message.answer(
        f"⭐ *DEPOSIT REQUEST SENT*\n{SEP}\n"
        f"💰 Amount: *₹{amount:,.2f}*\n"
        f"🆔 Request ID: *#{did}*\n\n"
        f"⏳ Waiting for admin approval...\n"
        f"Click below after payment:",
        parse_mode="Markdown",
        reply_markup=paid_confirm_kb(did)
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"⭐ *NEW STARS DEPOSIT*\n{SEP}\n"
                f"👤 User: @{uname} (`{user_id}`)\n"
                f"💰 Amount: *₹{amount:,.2f}*\n"
                f"🆔 Deposit ID: *#{did}*",
                parse_mode="Markdown",
                reply_markup=approve_reject_deposit_kb(did)
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")


async def process_upi_deposit(message: Message, bot: Bot, amount: float, txn_id: str):
    user_id = message.from_user.id
    did = await db.create_deposit(user_id, "upi", amount, txn_id)
    user = await db.get_user(user_id)
    uname = user.get("username", str(user_id)) if user else str(user_id)

    await message.answer(
        success_text(
            f"🏦 UPI Deposit Request Sent!\n"
            f"💰 Amount: ₹{amount:,.2f}\n"
            f"🔖 Txn ID: {txn_id}\n"
            f"🆔 Request ID: #{did}\n\n"
            f"⏳ Awaiting admin approval..."
        ),
        parse_mode="Markdown",
        reply_markup=back_kb()
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🏦 *NEW UPI DEPOSIT*\n{SEP}\n"
                f"👤 User: @{uname} (`{user_id}`)\n"
                f"💰 Amount: *₹{amount:,.2f}*\n"
                f"🔖 Txn ID: `{txn_id}`\n"
                f"🆔 Deposit ID: *#{did}*",
                parse_mode="Markdown",
                reply_markup=approve_reject_deposit_kb(did)
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")


async def approve_deposit(callback: CallbackQuery, bot: Bot, did: int):
    deposit = await db.get_deposit(did)
    if not deposit:
        await callback.answer("Deposit not found!", show_alert=True)
        return
    if deposit["status"] != "pending":
        await callback.answer("Already processed!", show_alert=True)
        return

    tax = deposit["amount"] * 0.05
    credited = deposit["amount"] - tax

    await db.update_deposit_status(did, "approved")
    await db.update_balance(deposit["user_id"], credited)
    await db.add_transaction(deposit["user_id"], "deposit", credited)

    await callback.message.edit_text(
        f"✅ *DEPOSIT APPROVED*\n{SEP}\n"
        f"🆔 ID: #{did}\n"
        f"💰 Amount: ₹{deposit['amount']:,.2f}\n"
        f"🧾 Tax (5%): -₹{tax:,.2f}\n"
        f"✅ Credited: ₹{credited:,.2f}",
        parse_mode="Markdown"
    )

    try:
        await bot.send_message(
            deposit["user_id"],
            success_text(
                f"Your deposit of ₹{deposit['amount']:,.2f} has been approved!\n"
                f"💰 Credited: ₹{credited:,.2f} (after 5% fee)"
            ),
            parse_mode="Markdown",
            reply_markup=back_kb()
        )
    except Exception as e:
        logger.error(f"Failed to notify user {deposit['user_id']}: {e}")

    await callback.answer("✅ Deposit approved!")
    logger.info(f"Deposit #{did} approved. Credited ₹{credited} to user {deposit['user_id']}")


async def reject_deposit(callback: CallbackQuery, bot: Bot, did: int):
    deposit = await db.get_deposit(did)
    if not deposit:
        await callback.answer("Deposit not found!", show_alert=True)
        return
    if deposit["status"] != "pending":
        await callback.answer("Already processed!", show_alert=True)
        return

    await db.update_deposit_status(did, "rejected")
    await callback.message.edit_text(
        f"❌ *DEPOSIT REJECTED*\n{SEP}\nID: #{did}",
        parse_mode="Markdown"
    )

    try:
        await bot.send_message(
            deposit["user_id"],
            error_text(f"Your deposit request #{did} has been rejected.\nContact support for help."),
            parse_mode="Markdown",
            reply_markup=back_kb()
        )
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")

    await callback.answer("❌ Deposit rejected!")
