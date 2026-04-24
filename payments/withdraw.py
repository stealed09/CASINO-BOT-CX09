from aiogram.types import Message, CallbackQuery
from aiogram import Bot
from database import db
from config import ADMIN_IDS
from ui.keyboards import approve_reject_withdraw_kb, back_kb
from ui.messages import success_text, error_text, SEP
from utils.logger import logger


async def process_upi_withdrawal(message: Message, bot: Bot, token_amount: float, upi_id: str):
    user_id = message.from_user.id
    withdraw_enabled = await db.get_setting("withdraw_enabled")
    if withdraw_enabled != "1":
        await message.answer(error_text("Withdrawals are currently disabled."), parse_mode="HTML", reply_markup=back_kb())
        return

    min_wd = float(await db.get_setting("min_withdrawal_tokens") or "100")
    user = await db.get_user(user_id)
    if not user:
        await message.answer(error_text("Please /start first."), parse_mode="HTML")
        return

    if user.get("is_banned"):
        await message.answer(error_text("Your account is banned."), parse_mode="HTML")
        return

    if token_amount < min_wd:
        await message.answer(
            error_text(f"Minimum withdrawal is {min_wd:,.2f} Tokens"),
            parse_mode="HTML", reply_markup=back_kb()
        )
        return

    wd_tax_pct = await db.get_effective_withdraw_tax(user_id)
    tax = round(token_amount * wd_tax_pct / 100, 4)
    after_tax = round(token_amount - tax, 4)

    if user["token_balance"] < token_amount:
        await message.answer(
            error_text(f"Insufficient balance.\nYour balance: {user['token_balance']:,.4f} Tokens"),
            parse_mode="HTML", reply_markup=back_kb()
        )
        return

    await db.update_token_balance(user_id, -token_amount)
    wid = await db.create_withdrawal(user_id, token_amount, method="upi", upi_id=upi_id)
    await db.add_transaction(user_id, "withdraw", token_amount, "pending", currency="TOKEN")

    uname = user.get("username", str(user_id))
    await message.answer(
        success_text(
            f"UPI Withdrawal Submitted!\n"
            f"🪙 Tokens: <b>{token_amount:,.4f}</b>\n"
            f"🧾 Tax ({wd_tax_pct}%): <b>-{tax:,.4f}</b>\n"
            f"💵 Net (paid out): <b>{after_tax:,.4f} Tokens worth</b>\n"
            f"🏦 UPI: <code>{upi_id}</code>\n"
            f"🆔 ID: #{wid}\n"
            f"⏳ Admin will process soon."
        ),
        parse_mode="HTML", reply_markup=back_kb()
    )

    inr_rate = float(await db.get_setting("inr_to_token_rate") or "1")
    inr_equiv = round(after_tax / inr_rate, 2) if inr_rate else after_tax

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"💸 <b>UPI WITHDRAWAL REQUEST</b>\n{SEP}\n"
                f"👤 @{uname} (<code>{user_id}</code>)\n"
                f"🪙 Tokens: {token_amount:,.4f} | Tax: {tax:,.4f} | Net: {after_tax:,.4f}\n"
                f"💵 ≈ ₹{inr_equiv:,.2f} to pay\n"
                f"🏦 UPI: <code>{upi_id}</code>\n"
                f"🆔 ID: <b>#{wid}</b>",
                parse_mode="HTML",
                reply_markup=approve_reject_withdraw_kb(wid)
            )
        except Exception as e:
            logger.error(f"Admin notify failed: {e}")


async def process_crypto_withdrawal(message: Message, bot: Bot,
                                     symbol: str, token_amount: float, address: str):
    user_id = message.from_user.id
    withdraw_enabled = await db.get_setting("withdraw_enabled")
    if withdraw_enabled != "1":
        await message.answer(error_text("Withdrawals disabled."), parse_mode="HTML", reply_markup=back_kb())
        return

    user = await db.get_user(user_id)
    if not user:
        await message.answer(error_text("Please /start first."), parse_mode="HTML")
        return

    if user.get("is_banned"):
        await message.answer(error_text("Your account is banned."), parse_mode="HTML")
        return

    min_wd = float(await db.get_setting("min_withdrawal_tokens") or "100")
    if token_amount < min_wd:
        await message.answer(
            error_text(f"Minimum withdrawal is {min_wd:,.2f} Tokens"),
            parse_mode="HTML", reply_markup=back_kb()
        )
        return

    if user["token_balance"] < token_amount:
        await message.answer(
            error_text(f"Insufficient balance.\nYour balance: {user['token_balance']:,.4f} Tokens"),
            parse_mode="HTML", reply_markup=back_kb()
        )
        return

    wd_tax_pct = await db.get_effective_withdraw_tax(user_id)
    tax = round(token_amount * wd_tax_pct / 100, 4)
    after_tax = round(token_amount - tax, 4)

    # Convert tokens to crypto
    rate_key = f"crypto_to_token_rate_{symbol.upper()}"
    rate = float(await db.get_setting(rate_key) or "85")
    crypto_equiv = round(after_tax / rate, 6) if rate else 0

    crypto = await db.get_crypto(symbol)
    network = crypto["network"] if crypto else symbol

    await db.update_token_balance(user_id, -token_amount)
    wid = await db.create_withdrawal(
        user_id, token_amount, method="crypto",
        crypto_currency=symbol, crypto_address=address, crypto_network=network
    )
    await db.add_transaction(user_id, "crypto_withdraw", token_amount, "pending", currency="TOKEN")

    uname = user.get("username", str(user_id))
    await message.answer(
        success_text(
            f"Crypto Withdrawal Submitted!\n"
            f"🪙 Tokens: <b>{token_amount:,.4f}</b>\n"
            f"🧾 Tax ({wd_tax_pct}%): <b>-{tax:,.4f}</b>\n"
            f"💵 Net Tokens: <b>{after_tax:,.4f}</b>\n"
            f"₿ ≈ {crypto_equiv:.6f} {symbol} to receive\n"
            f"📬 Address: <code>{address}</code>\n"
            f"🆔 ID: #{wid}"
        ),
        parse_mode="HTML", reply_markup=back_kb()
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"₿ <b>CRYPTO WITHDRAWAL REQUEST</b>\n{SEP}\n"
                f"👤 @{uname} (<code>{user_id}</code>)\n"
                f"🪙 {token_amount:,.4f} Tokens | Net: {after_tax:,.4f}\n"
                f"₿ Send ≈ {crypto_equiv:.6f} {symbol} ({network})\n"
                f"📬 Address: <code>{address}</code>\n"
                f"🆔 ID: <b>#{wid}</b>",
                parse_mode="HTML",
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

    user_id = wd["user_id"]
    wd_tax_pct = await db.get_effective_withdraw_tax(user_id)
    tax = round(wd["token_amount"] * wd_tax_pct / 100, 4)
    after_tax = round(wd["token_amount"] - tax, 4)
    method = wd.get("method", "upi")

    await db.update_withdrawal_status(wid, "paid")

    try:
        await callback.message.edit_text(
            f"✅ <b>WITHDRAWAL PAID</b> #{wid}\n"
            f"🪙 {wd['token_amount']:,.4f} Tokens | Net: {after_tax:,.4f}",
            parse_mode="HTML"
        )
    except:
        pass

    dest = f"UPI: {wd['upi_id']}" if method == "upi" else f"Address: {wd['crypto_address']}"
    try:
        await bot.send_message(
            user_id,
            success_text(
                f"Withdrawal Paid! 🎉\n"
                f"🪙 Tokens: {wd['token_amount']:,.4f}\n"
                f"✅ Net: {after_tax:,.4f}\n"
                f"📬 {dest}"
            ),
            parse_mode="HTML", reply_markup=back_kb()
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

    # Refund tokens
    await db.update_token_balance(wd["user_id"], wd["token_amount"])
    await db.add_transaction(wd["user_id"], "refund", wd["token_amount"], "refund", currency="TOKEN")
    await db.update_withdrawal_status(wid, "rejected")

    try:
        await callback.message.edit_text(f"❌ Withdrawal #{wid} rejected & refunded.", parse_mode="HTML")
    except:
        pass

    try:
        await bot.send_message(
            wd["user_id"],
            error_text(
                f"Withdrawal #{wid} rejected.\n"
                f"🪙 {wd['token_amount']:,.4f} Tokens refunded to your balance."
            ),
            parse_mode="HTML", reply_markup=back_kb()
        )
    except Exception as e:
        logger.error(f"User notify failed: {e}")
    await callback.answer("❌ Rejected & Refunded!")
