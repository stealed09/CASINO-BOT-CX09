from aiogram.types import Message, CallbackQuery
from aiogram import Bot
from database import db
from config import ADMIN_IDS
from ui.keyboards import approve_reject_withdraw_kb, back_kb
from ui.messages import success_text, error_text, SEP
from utils.logger import logger


async def process_inr_withdrawal(message: Message, bot: Bot, amount: float, upi_id: str):
    user_id = message.from_user.id
    withdraw_enabled = await db.get_setting("withdraw_enabled")
    if withdraw_enabled != "1":
        await message.answer(error_text("Withdrawals disabled."), parse_mode="Markdown", reply_markup=back_kb()); return

    min_wd = float(await db.get_setting("min_withdrawal") or "100")
    user = await db.get_user(user_id)
    if not user:
        await message.answer(error_text("Please /start first."), parse_mode="Markdown"); return

    if amount < min_wd:
        await message.answer(error_text(f"Minimum withdrawal is ₹{min_wd:,.2f}"), parse_mode="Markdown", reply_markup=back_kb()); return

    wd_tax_pct = float(await db.get_setting("withdrawal_tax") or "0")
    tax = round(amount * wd_tax_pct / 100, 2)
    after_tax = round(amount - tax, 2)

    if user["balance"] < amount:
        await message.answer(error_text(f"Insufficient balance. Your balance: ₹{user['balance']:,.2f}"), parse_mode="Markdown", reply_markup=back_kb()); return

    await db.update_balance(user_id, -amount)
    wid = await db.create_withdrawal(user_id, amount, "INR", upi_id=upi_id)
    await db.add_transaction(user_id, "withdraw", amount, "pending", currency="INR")

    uname = user.get("username", str(user_id))
    await message.answer(
        success_text(
            f"INR Withdrawal submitted!\n"
            f"💰 Amount: ₹{amount:,.2f}\n"
            f"🧾 Tax ({wd_tax_pct}%): -₹{tax:,.2f}\n"
            f"💵 You'll receive: ₹{after_tax:,.2f}\n"
            f"🏦 UPI: {upi_id}\n🆔 ID: #{wid}"
        ),
        parse_mode="Markdown", reply_markup=back_kb()
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"💸 *INR WITHDRAWAL*\n{SEP}\n"
                f"👤 @{uname} (`{user_id}`)\n"
                f"💰 ₹{amount:,.2f} | Tax: ₹{tax:,.2f} | Net: ₹{after_tax:,.2f}\n"
                f"🏦 UPI: `{upi_id}`\n🆔 ID: *#{wid}*",
                parse_mode="Markdown",
                reply_markup=approve_reject_withdraw_kb(wid)
            )
        except Exception as e:
            logger.error(f"Admin notify failed: {e}")


async def process_crypto_withdrawal(message: Message, bot: Bot, symbol: str, amount: float, address: str):
    user_id = message.from_user.id
    withdraw_enabled = await db.get_setting("withdraw_enabled")
    if withdraw_enabled != "1":
        await message.answer(error_text("Withdrawals disabled."), parse_mode="Markdown", reply_markup=back_kb()); return

    crypto = await db.get_crypto(symbol)
    if not crypto:
        await message.answer(error_text("Invalid crypto."), parse_mode="Markdown"); return

    bal = await db.get_crypto_balance(user_id, symbol)
    if bal < amount:
        await message.answer(error_text(f"Insufficient {symbol} balance.\nYou have: {bal:.6f} {symbol}"), parse_mode="Markdown"); return

    wd_tax_pct = float(await db.get_setting("withdrawal_tax") or "0")
    tax = round(amount * wd_tax_pct / 100, 6)
    after_tax = round(amount - tax, 6)

    await db.update_crypto_balance(user_id, symbol, -amount)
    wid = await db.create_withdrawal(
        user_id, amount, symbol,
        crypto_address=address, crypto_network=crypto["network"]
    )
    await db.add_transaction(user_id, "crypto_withdraw", amount, "pending", currency=symbol)

    user = await db.get_user(user_id)
    uname = user.get("username", str(user_id)) if user else str(user_id)

    await message.answer(
        success_text(
            f"Crypto Withdrawal submitted!\n"
            f"🪙 {symbol} ({crypto['network']})\n"
            f"💰 Amount: {amount:.6f} {symbol}\n"
            f"🧾 Tax ({wd_tax_pct}%): -{tax:.6f} {symbol}\n"
            f"💵 Net: {after_tax:.6f} {symbol}\n"
            f"📬 Address: `{address}`\n🆔 ID: #{wid}"
        ),
        parse_mode="Markdown", reply_markup=back_kb()
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"₿ *CRYPTO WITHDRAWAL*\n{SEP}\n"
                f"👤 @{uname} (`{user_id}`)\n"
                f"🪙 {symbol} ({crypto['network']})\n"
                f"💰 {amount:.6f} | Net: {after_tax:.6f}\n"
                f"📬 Address: `{address}`\n🆔 ID: *#{wid}*",
                parse_mode="Markdown",
                reply_markup=approve_reject_withdraw_kb(wid)
            )
        except Exception as e:
            logger.error(f"Admin notify failed: {e}")


async def approve_withdrawal(callback: CallbackQuery, bot: Bot, wid: int):
    wd = await db.get_withdrawal(wid)
    if not wd:
        await callback.answer("Not found!", show_alert=True); return
    if wd["status"] != "pending":
        await callback.answer("Already processed!", show_alert=True); return

    currency = wd.get("currency", "INR")
    wd_tax_pct = float(await db.get_setting("withdrawal_tax") or "0")
    tax = round(wd["amount"] * wd_tax_pct / 100, 6)
    after_tax = round(wd["amount"] - tax, 6)
    sym = "₹" if currency == "INR" else currency

    await db.update_withdrawal_status(wid, "paid")
    try:
        await callback.message.edit_text(
            f"✅ *WITHDRAWAL PAID* #{wid}\n{sym}{wd['amount']:,.6f} | Net: {sym}{after_tax:,.6f}",
            parse_mode="Markdown"
        )
    except:
        pass

    try:
        await bot.send_message(
            wd["user_id"],
            success_text(
                f"Withdrawal paid!\n"
                f"💰 {sym}{wd['amount']:,.6f} | Net: {sym}{after_tax:,.6f}\n"
                f"{'🏦 UPI: ' + wd['upi_id'] if currency == 'INR' else '📬 Address: ' + wd['crypto_address']}"
            ),
            parse_mode="Markdown", reply_markup=back_kb()
        )
    except Exception as e:
        logger.error(f"User notify failed: {e}")
    await callback.answer("✅ Paid!")


async def reject_withdrawal(callback: CallbackQuery, bot: Bot, wid: int):
    wd = await db.get_withdrawal(wid)
    if not wd:
        await callback.answer("Not found!", show_alert=True); return
    if wd["status"] != "pending":
        await callback.answer("Already processed!", show_alert=True); return

    currency = wd.get("currency", "INR")
    sym = "₹" if currency == "INR" else currency

    # Refund
    if currency == "INR":
        await db.update_balance(wd["user_id"], wd["amount"])
        await db.add_transaction(wd["user_id"], "deposit", wd["amount"], "refund", currency="INR")
    else:
        await db.update_crypto_balance(wd["user_id"], currency, wd["amount"])
        await db.add_transaction(wd["user_id"], "crypto_deposit", wd["amount"], "refund", currency=currency)

    await db.update_withdrawal_status(wid, "rejected")
    try:
        await callback.message.edit_text(f"❌ Withdrawal #{wid} rejected & refunded.", parse_mode="Markdown")
    except:
        pass

    try:
        await bot.send_message(
            wd["user_id"],
            error_text(f"Withdrawal #{wid} rejected.\n{sym}{wd['amount']:,.6f} refunded."),
            parse_mode="Markdown", reply_markup=back_kb()
        )
    except Exception as e:
        logger.error(f"User notify failed: {e}")
    await callback.answer("❌ Rejected & refunded!")
