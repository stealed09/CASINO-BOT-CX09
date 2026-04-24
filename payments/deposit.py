import io
import asyncio
import qrcode
from aiogram.types import Message, CallbackQuery, LabeledPrice, BufferedInputFile
from aiogram import Bot
from database import db
from config import ADMIN_IDS
from ui.keyboards import (
    approve_reject_deposit_kb, back_kb, upi_paid_done_kb,
    deposit_method_kb, nowpayments_currency_kb
)
from ui.messages import success_text, error_text, SEP
from utils.logger import logger
from payments.nowpayments import (
    create_payment, get_payment_status,
    FINISHED_STATUSES, FAILED_STATUSES
)


async def generate_upi_qr(upi_id: str, amount: float) -> BufferedInputFile:
    upi_string = f"upi://pay?pa={upi_id}&am={amount:.2f}&cu=INR"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(upi_string)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return BufferedInputFile(buf.read(), filename="upi_qr.png")


async def calculate_tokens_for_inr(user_id: int, inr_amount: float) -> tuple[float, float, float]:
    """Returns (gross_tokens, tax_tokens, net_tokens)"""
    rate = float(await db.get_setting("inr_to_token_rate") or "1")
    dep_tax_pct = await db.get_effective_deposit_tax(user_id)
    gross = round(inr_amount * rate, 4)
    tax = round(gross * dep_tax_pct / 100, 4)
    net = round(gross - tax, 4)
    return gross, tax, net


async def calculate_tokens_for_crypto(user_id: int, symbol: str, crypto_amount: float) -> tuple[float, float, float]:
    """Returns (gross_tokens, tax_tokens, net_tokens)"""
    rate_key = f"crypto_to_token_rate_{symbol.upper()}"
    rate = float(await db.get_setting(rate_key) or "85")
    dep_tax_pct = await db.get_effective_deposit_tax(user_id)
    gross = round(crypto_amount * rate, 4)
    tax = round(gross * dep_tax_pct / 100, 4)
    net = round(gross - tax, 4)
    return gross, tax, net


async def calculate_tokens_for_stars(user_id: int, stars: int) -> tuple[float, float, float]:
    """Returns (gross_tokens, tax_tokens, net_tokens)"""
    rate = float(await db.get_setting("stars_to_token_rate") or "1")
    dep_tax_pct = await db.get_effective_deposit_tax(user_id)
    gross = round(stars * rate, 4)
    tax = round(gross * dep_tax_pct / 100, 4)
    net = round(gross - tax, 4)
    return gross, tax, net


# ─── UPI DEPOSIT ──────────────────────────────────────────────────────────────

async def start_upi_deposit(message: Message, bot: Bot, inr_amount: float):
    user_id = message.from_user.id
    upi_id = await db.get_setting("upi_id") or "notset@upi"
    dep_tax_pct = await db.get_effective_deposit_tax(user_id)
    gross, tax, net = await calculate_tokens_for_inr(user_id, inr_amount)
    rate = float(await db.get_setting("inr_to_token_rate") or "1")

    did = await db.create_deposit(user_id, "upi", inr_amount=inr_amount)

    caption = (
        f"🏦 *UPI DEPOSIT*\n{SEP}\n"
        f"💵 INR Amount: *₹{inr_amount:,.2f}*\n"
        f"🏦 UPI ID: `{upi_id}`\n"
        f"📊 Rate: ₹1 = *{rate} Tokens*\n"
        f"🪙 Gross Tokens: *{gross:,.4f}*\n"
        f"🧾 Tax ({dep_tax_pct}%): *-{tax:,.4f}*\n"
        f"✅ You'll Receive: *{net:,.4f} Tokens*\n"
        f"{SEP}\n"
        f"📌 Scan QR or pay to UPI ID above\n"
        f"Then click ✅ *Payment Done*\n"
        f"🆔 Request ID: *#{did}*"
    )

    try:
        qr_file = await generate_upi_qr(upi_id, inr_amount)
        await message.answer_photo(
            photo=qr_file,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=upi_paid_done_kb(did)
        )
    except Exception as e:
        logger.error(f"QR generation error: {e}")
        await message.answer(caption, parse_mode="Markdown", reply_markup=upi_paid_done_kb(did))


# ─── STARS DEPOSIT ─────────────────────────────────────────────────────────────

async def show_deposit_stars(callback: CallbackQuery):
    await callback.answer()
    dep_tax = await db.get_effective_deposit_tax(callback.from_user.id)
    rate = await db.get_setting("stars_to_token_rate") or "1"
    try:
        await callback.message.edit_text(
            f"⭐ *STARS DEPOSIT*\n{SEP}\n"
            f"📊 Rate: 1 Star = *{rate} Token(s)*\n"
            f"🧾 Tax: *{dep_tax}%*\n\n"
            f"Send the number of ⭐ Stars you want to pay:\nExample: `100`",
            parse_mode="Markdown",
            reply_markup=back_kb("wallet_deposit")
        )
    except:
        await callback.message.answer("Send number of Stars:", reply_markup=back_kb("wallet_deposit"))


async def send_stars_invoice(message: Message, bot: Bot, stars_count: int):
    did = await db.create_deposit(message.from_user.id, "stars", stars_amount=stars_count)
    try:
        await bot.send_invoice(
            chat_id=message.chat.id,
            title="⭐ Token Purchase",
            description=f"Buy tokens with {stars_count} Telegram Stars",
            payload=f"deposit_{did}_{message.from_user.id}",
            currency="XTR",
            prices=[LabeledPrice(label=f"{stars_count} Stars", amount=stars_count)],
        )
    except Exception as e:
        logger.error(f"Stars invoice error: {e}")
        await message.answer(error_text(f"Stars payment error: {e}"), parse_mode="Markdown")


async def process_stars_payment(pre_checkout_query, bot: Bot):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


async def handle_successful_payment(message: Message, bot: Bot):
    payload = message.successful_payment.invoice_payload
    stars_paid = message.successful_payment.total_amount
    try:
        parts = payload.split("_")
        did = int(parts[1])
        user_id = int(parts[2])
    except:
        logger.error(f"Bad payment payload: {payload}")
        return

    gross, tax, net = await calculate_tokens_for_stars(user_id, stars_paid)

    await db.update_deposit_status(did, "approved", token_credited=net)
    await db.update_token_balance(user_id, net)
    await db.add_transaction(user_id, "deposit", net, currency="TOKEN")

    dep_tax = await db.get_effective_deposit_tax(user_id)
    await message.answer(
        success_text(
            f"⭐ Stars Payment Confirmed!\n"
            f"⭐ Stars Paid: *{stars_paid}*\n"
            f"🪙 Gross Tokens: *{gross:,.4f}*\n"
            f"🧾 Tax ({dep_tax}%): *-{tax:,.4f}*\n"
            f"✅ Tokens Credited: *{net:,.4f}*"
        ),
        parse_mode="Markdown", reply_markup=back_kb()
    )

    user = await db.get_user(user_id)
    uname = user.get("username", str(user_id)) if user else str(user_id)
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"⭐ *STARS DEPOSIT AUTO-APPROVED*\n{SEP}\n"
                f"👤 @{uname} (`{user_id}`)\n"
                f"⭐ {stars_paid} Stars → 🪙 {net:,.4f} Tokens",
                parse_mode="Markdown"
            )
        except:
            pass


# ─── NOWPAYMENTS CRYPTO DEPOSIT ───────────────────────────────────────────────

NOWPAYMENTS_POPULAR = ["usdttrc20", "usdterc20", "btc", "eth", "ltc", "bnb", "trx", "doge"]


async def start_nowpayments_deposit(callback: CallbackQuery, state, token_amount: float):
    """Show currency selection for NowPayments deposit."""
    await callback.answer()
    try:
        await callback.message.edit_text(
            f"₿ *CRYPTO DEPOSIT (Auto)*\n{SEP}\n"
            f"🪙 Tokens to receive: *{token_amount:,.4f}*\n"
            f"⚡ Auto-confirmed via NowPayments\n\n"
            f"Choose crypto currency to pay:",
            parse_mode="Markdown",
            reply_markup=nowpayments_currency_kb(token_amount)
        )
    except:
        await callback.message.answer("Choose crypto:", reply_markup=nowpayments_currency_kb(token_amount))


async def create_nowpayments_deposit(message: Message, bot: Bot,
                                      user_id: int, pay_currency: str, token_amount: float):
    """Create NowPayments invoice and store it."""
    dep_tax_pct = await db.get_effective_deposit_tax(user_id)
    tax = round(token_amount * dep_tax_pct / 100, 4)
    net_tokens = round(token_amount - tax, 4)

    # Create deposit record first to get ID
    did = await db.create_deposit(
        user_id, "nowpayments",
        crypto_currency=pay_currency.upper(),
        crypto_amount=0  # will be filled by API
    )

    # Convert token amount to approximate USD for NowPayments
    # 1 token = 1 INR ≈ 0.012 USD (approx)
    usd_amount = round(token_amount / 85, 4)  # rough conversion, admin sets token rate

    result = await create_payment(
        pay_currency=pay_currency,
        price_amount=max(usd_amount, 0.5),  # NowPayments minimum $0.5
        order_id=f"casino_{did}",
        order_description=f"Casino Token Deposit #{did}"
    )

    if not result:
        await message.answer(
            error_text("Failed to create payment. Try again or contact support."),
            parse_mode="Markdown"
        )
        return

    payment_id = result.get("payment_id", "")
    pay_address = result.get("pay_address", "")
    actual_pay_amount = result.get("pay_amount", 0)
    actual_pay_currency = result.get("pay_currency", pay_currency)

    # Store NowPayments order
    await db.create_nowpayments_order(
        deposit_id=did, user_id=user_id,
        payment_id=str(payment_id),
        pay_currency=actual_pay_currency,
        pay_amount=actual_pay_amount,
        pay_address=pay_address
    )

    await message.answer(
        f"₿ *CRYPTO PAYMENT CREATED*\n{SEP}\n"
        f"🪙 Currency: *{actual_pay_currency.upper()}*\n"
        f"💰 Send Exactly: *{actual_pay_amount} {actual_pay_currency.upper()}*\n"
        f"📬 Address:\n`{pay_address}`\n"
        f"{SEP}\n"
        f"📊 Token Breakdown:\n"
        f"🪙 Gross: *{token_amount:,.4f}* Tokens\n"
        f"🧾 Tax ({dep_tax_pct}%): *-{tax:,.4f}*\n"
        f"✅ Net Tokens: *{net_tokens:,.4f}*\n"
        f"{SEP}\n"
        f"⏳ Payment auto-detects in ~5 min\n"
        f"⚠️ Send EXACT amount on correct network\n"
        f"🆔 Order ID: *#{did}*  |  Payment: `{payment_id}`",
        parse_mode="Markdown",
        reply_markup=back_kb()
    )

    user = await db.get_user(user_id)
    uname = user.get("username", str(user_id)) if user else str(user_id)
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"₿ *NOWPAYMENTS DEPOSIT CREATED*\n{SEP}\n"
                f"👤 @{uname} (`{user_id}`)\n"
                f"💰 {actual_pay_amount} {actual_pay_currency.upper()}\n"
                f"🪙 Net Tokens: {net_tokens:,.4f}\n"
                f"🆔 Deposit: #{did} | Payment: {payment_id}",
                parse_mode="Markdown"
            )
        except:
            pass


async def poll_nowpayments_status(bot: Bot, payment_id: str):
    """
    Poll NowPayments for payment confirmation.
    Call this in a background task after creating payment.
    """
    order = await db.get_nowpayments_order(payment_id)
    if not order:
        return

    for _ in range(60):  # poll for up to 30 minutes
        await asyncio.sleep(30)

        status_data = await get_payment_status(payment_id)
        if not status_data:
            continue

        status = status_data.get("payment_status", "")
        await db.update_nowpayments_status(payment_id, status)

        if status in FINISHED_STATUSES:
            deposit = await db.get_deposit(order["deposit_id"])
            if not deposit or deposit["status"] != "pending":
                return

            user_id = order["user_id"]
            token_amount = deposit.get("token_credited", 0)

            # If token_credited not set yet, recalculate
            if not token_amount:
                dep_tax_pct = await db.get_effective_deposit_tax(user_id)
                # Use inr_amount as token base if set
                base = deposit.get("inr_amount") or deposit.get("crypto_amount") or 0
                rate_key = f"crypto_to_token_rate_{order['pay_currency'].upper()}"
                rate = float(await db.get_setting(rate_key) or "85")
                gross = round(base * rate, 4) if base else round(order["pay_amount"] * rate, 4)
                tax = round(gross * dep_tax_pct / 100, 4)
                token_amount = round(gross - tax, 4)

            await db.update_deposit_status(order["deposit_id"], "approved", token_credited=token_amount)
            await db.update_token_balance(user_id, token_amount)
            await db.add_transaction(user_id, "crypto_deposit", token_amount, currency="TOKEN")

            user = await db.get_user(user_id)
            uname = user.get("username", str(user_id)) if user else str(user_id)

            try:
                await bot.send_message(
                    user_id,
                    success_text(
                        f"₿ Crypto Payment Confirmed!\n"
                        f"💰 {order['pay_amount']} {order['pay_currency'].upper()}\n"
                        f"✅ Tokens Credited: *{token_amount:,.4f}*"
                    ),
                    parse_mode="Markdown"
                )
            except:
                pass

            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(
                        admin_id,
                        f"✅ *NOWPAYMENTS CONFIRMED*\n{SEP}\n"
                        f"👤 @{uname} (`{user_id}`)\n"
                        f"🪙 {token_amount:,.4f} Tokens credited\n"
                        f"Payment: {payment_id}",
                        parse_mode="Markdown"
                    )
                except:
                    pass
            return

        elif status in FAILED_STATUSES:
            deposit = await db.get_deposit(order["deposit_id"])
            if deposit and deposit["status"] == "pending":
                await db.update_deposit_status(order["deposit_id"], "rejected")
            user_id = order["user_id"]
            try:
                await bot.send_message(
                    user_id,
                    error_text(f"Crypto payment {status}.\nDeposit #{order['deposit_id']} cancelled."),
                    parse_mode="Markdown"
                )
            except:
                pass
            return


# ─── MANUAL ADMIN APPROVE/REJECT ──────────────────────────────────────────────

async def approve_deposit(callback: CallbackQuery, bot: Bot, did: int):
    deposit = await db.get_deposit(did)
    if not deposit:
        await callback.answer("Not found!", show_alert=True); return
    if deposit["status"] != "pending":
        await callback.answer("Already processed!", show_alert=True); return

    user_id = deposit["user_id"]
    method = deposit.get("method", "upi")
    dep_tax_pct = await db.get_effective_deposit_tax(user_id)

    # Calculate tokens based on method
    if method in ("upi", "stars"):
        inr = deposit.get("inr_amount", 0) or deposit.get("stars_amount", 0)
        if method == "stars":
            gross, tax, net = await calculate_tokens_for_stars(user_id, int(inr))
        else:
            gross, tax, net = await calculate_tokens_for_inr(user_id, float(inr))
    elif method in ("crypto", "nowpayments"):
        sym = deposit.get("crypto_currency", "USDT")
        amt = deposit.get("crypto_amount", 0)
        gross, tax, net = await calculate_tokens_for_crypto(user_id, sym, float(amt))
    else:
        gross, tax, net = 0, 0, 0

    await db.update_deposit_status(did, "approved", token_credited=net)
    await db.update_token_balance(user_id, net)
    await db.add_transaction(user_id, "deposit", net, currency="TOKEN")

    try:
        await callback.message.edit_caption(
            f"✅ *DEPOSIT APPROVED* #{did}\n"
            f"🪙 Tokens: {net:,.4f} (Tax: {dep_tax_pct}%)",
            parse_mode="Markdown"
        )
    except:
        try:
            await callback.message.edit_text(
                f"✅ *DEPOSIT APPROVED* #{did}\n🪙 {net:,.4f} Tokens",
                parse_mode="Markdown"
            )
        except:
            pass

    try:
        await bot.send_message(
            user_id,
            success_text(
                f"Deposit #{did} approved!\n"
                f"🪙 Gross: {gross:,.4f} Tokens\n"
                f"🧾 Tax ({dep_tax_pct}%): -{tax:,.4f}\n"
                f"✅ Credited: *{net:,.4f} Tokens*"
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"User notify failed: {e}")
    await callback.answer("✅ Approved!")


async def reject_deposit(callback: CallbackQuery, bot: Bot, did: int):
    deposit = await db.get_deposit(did)
    if not deposit:
        await callback.answer("Not found!", show_alert=True); return
    if deposit["status"] != "pending":
        await callback.answer("Already processed!", show_alert=True); return

    await db.update_deposit_status(did, "rejected")
    try:
        await callback.message.edit_caption(f"❌ Deposit #{did} rejected.")
    except:
        try:
            await callback.message.edit_text(f"❌ Deposit #{did} rejected.")
        except:
            pass
    try:
        await bot.send_message(
            deposit["user_id"],
            error_text(f"Deposit #{did} rejected. Contact support."),
            parse_mode="Markdown"
        )
    except:
        pass
    await callback.answer("❌ Rejected!")
