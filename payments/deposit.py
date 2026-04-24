import io
import asyncio
import qrcode
from aiogram.types import Message, CallbackQuery, LabeledPrice, BufferedInputFile
from aiogram import Bot
from database import db
from config import ADMIN_IDS
from ui.keyboards import (
    approve_reject_deposit_kb, back_kb, upi_paid_done_kb,
    deposit_method_kb, oxapay_currency_kb
)
from ui.messages import success_text, error_text, SEP
from utils.logger import logger
from payments.oxapay import (
    create_invoice, check_payment, OXAPAY_CURRENCIES,
    PAID_STATUSES, FAILED_STATUSES
)


# ─── TOKEN CALCULATION ─────────────────────────────────────────────────────────
# Universal rule: $1 USD = usd_to_token_rate Tokens (default 85)
# INR: ₹1 = inr_to_token_rate Tokens (default 1)
# Stars: 1 Star = stars_to_token_rate Tokens (default 1)
# Crypto: always converted via USD rate

async def get_usd_token_rate() -> float:
    return float(await db.get_setting("usd_to_token_rate") or "85")

async def get_inr_token_rate() -> float:
    return float(await db.get_setting("inr_to_token_rate") or "1")

async def get_stars_token_rate() -> float:
    return float(await db.get_setting("stars_to_token_rate") or "1")

async def _apply_tax(user_id: int, gross: float):
    dep_tax_pct = await db.get_effective_deposit_tax(user_id)
    tax = round(gross * dep_tax_pct / 100, 4)
    net = round(gross - tax, 4)
    return dep_tax_pct, tax, net

async def tokens_for_usd(user_id: int, usd: float):
    rate = await get_usd_token_rate()
    gross = round(usd * rate, 4)
    dep_tax_pct, tax, net = await _apply_tax(user_id, gross)
    return gross, tax, net, dep_tax_pct

async def tokens_for_inr(user_id: int, inr: float):
    rate = await get_inr_token_rate()
    gross = round(inr * rate, 4)
    dep_tax_pct, tax, net = await _apply_tax(user_id, gross)
    return gross, tax, net, dep_tax_pct

async def tokens_for_stars(user_id: int, stars: int):
    rate = await get_stars_token_rate()
    gross = round(stars * rate, 4)
    dep_tax_pct, tax, net = await _apply_tax(user_id, gross)
    return gross, tax, net, dep_tax_pct


# ─── UPI DEPOSIT ──────────────────────────────────────────────────────────────

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


async def start_upi_deposit(message: Message, bot: Bot, inr_amount: float):
    user_id = message.from_user.id
    upi_id = await db.get_setting("upi_id") or "notset@upi"
    gross, tax, net, dep_tax_pct = await tokens_for_inr(user_id, inr_amount)
    rate = await get_inr_token_rate()
    did = await db.create_deposit(user_id, "upi", inr_amount=inr_amount)

    caption = (
        f"🏦 <b>UPI DEPOSIT</b>\n{SEP}\n"
        f"💵 Amount: <b>₹{inr_amount:,.2f} INR</b>\n"
        f"🏦 UPI ID: <code>{upi_id}</code>\n"
        f"{SEP}\n"
        f"📊 Rate: ₹1 = <b>{rate} Tokens</b>\n"
        f"🪙 Gross Tokens: <b>{gross:,.4f}</b>\n"
        f"🧾 Tax ({dep_tax_pct}%): <b>-{tax:,.4f}</b>\n"
        f"✅ You Receive: <b>{net:,.4f} Tokens</b>\n"
        f"{SEP}\n"
        f"📌 Scan QR or pay to UPI ID above\n"
        f"Then click ✅ <b>Payment Done</b>\n"
        f"🆔 Request ID: <b>#{did}</b>"
    )
    try:
        qr_file = await generate_upi_qr(upi_id, inr_amount)
        await message.answer_photo(photo=qr_file, caption=caption,
                                    parse_mode="HTML", reply_markup=upi_paid_done_kb(did))
    except Exception as e:
        logger.error(f"QR error: {e}")
        await message.answer(caption, parse_mode="HTML", reply_markup=upi_paid_done_kb(did))


# ─── STARS DEPOSIT ─────────────────────────────────────────────────────────────

async def show_deposit_stars(callback: CallbackQuery):
    await callback.answer()
    rate = await get_stars_token_rate()
    dep_tax = await db.get_effective_deposit_tax(callback.from_user.id)
    try:
        await callback.message.edit_text(
            f"⭐ <b>STARS DEPOSIT</b>\n{SEP}\n"
            f"📊 Rate: 1 ⭐ Star = <b>{rate} Token(s)</b>\n"
            f"🧾 Tax: <b>{dep_tax}%</b>\n\n"
            f"Send number of ⭐ Stars to pay:\nExample: <code>100</code>",
            parse_mode="HTML", reply_markup=back_kb("wallet_deposit")
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
        await message.answer(error_text(f"Stars error: {e}"), parse_mode="HTML")


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

    gross, tax, net, dep_tax_pct = await tokens_for_stars(user_id, stars_paid)
    await db.update_deposit_status(did, "approved", token_credited=net)
    await db.update_token_balance(user_id, net)
    await db.add_transaction(user_id, "deposit", net, currency="TOKEN")

    rate = await get_stars_token_rate()
    await message.answer(
        success_text(
            f"⭐ Stars Payment Confirmed!\n"
            f"⭐ Stars Paid: <b>{stars_paid}</b>\n"
            f"📊 Rate: 1 ⭐ = <b>{rate} Tokens</b>\n"
            f"🪙 Gross Tokens: <b>{gross:,.4f}</b>\n"
            f"🧾 Tax ({dep_tax_pct}%): <b>-{tax:,.4f}</b>\n"
            f"✅ Tokens Credited: <b>{net:,.4f}</b>"
        ),
        parse_mode="HTML", reply_markup=back_kb()
    )

    user = await db.get_user(user_id)
    uname = user.get("username", str(user_id)) if user else str(user_id)
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"⭐ <b>STARS DEPOSIT AUTO-APPROVED</b>\n{SEP}\n"
                f"👤 @{uname} (<code>{user_id}</code>)\n"
                f"⭐ {stars_paid} Stars → 🪙 {net:,.4f} Tokens",
                parse_mode="HTML"
            )
        except:
            pass


# ─── OXAPAY CRYPTO DEPOSIT ─────────────────────────────────────────────────────

async def start_oxapay_deposit(callback: CallbackQuery, token_amount: float):
    """Show crypto currency selection."""
    await callback.answer()
    rate = await get_usd_token_rate()
    usd_amount = round(token_amount / rate, 4)
    try:
        await callback.message.edit_text(
            f"₿ <b>CRYPTO DEPOSIT</b>\n{SEP}\n"
            f"🪙 Tokens to buy: <b>{token_amount:,.0f}</b>\n"
            f"📊 Rate: $1 = <b>{rate} Tokens</b>\n"
            f"💵 USD equivalent: <b>${usd_amount:.2f}</b>\n"
            f"⚡ Auto-confirmed via Oxapay\n\n"
            f"Choose crypto to pay with:",
            parse_mode="HTML",
            reply_markup=oxapay_currency_kb(token_amount)
        )
    except:
        await callback.message.answer("Choose crypto:", reply_markup=oxapay_currency_kb(token_amount))


async def create_oxapay_deposit(message: Message, bot: Bot,
                                  user_id: int, currency: str, network: str, token_amount: float):
    """Create Oxapay invoice and send payment instructions."""
    rate = await get_usd_token_rate()
    dep_tax_pct = await db.get_effective_deposit_tax(user_id)
    usd_amount = max(round(token_amount / rate, 2), 1.0)  # min $1

    # Tax applied on token side
    gross_tokens = token_amount
    tax_tokens = round(gross_tokens * dep_tax_pct / 100, 4)
    net_tokens = round(gross_tokens - tax_tokens, 4)

    did = await db.create_deposit(
        user_id, "oxapay",
        crypto_currency=f"{currency}_{network}",
        crypto_amount=usd_amount
    )

    result = await create_invoice(
        amount_usd=usd_amount,
        currency=currency,
        network=network,
        order_id=f"casino_{did}",
        description=f"Token Deposit #{did}"
    )

    if not result:
        await message.answer(
            error_text(
                "Failed to create payment.\n\n"
                "Possible reasons:\n"
                "• Invalid Oxapay merchant key\n"
                "• Check Admin → Settings → Oxapay Key\n\n"
                "Contact admin if issue persists."
            ),
            parse_mode="HTML"
        )
        return

    pay_address = result.get("address", "")
    pay_amount  = result.get("amount", usd_amount)
    track_id    = str(result.get("trackId", ""))
    expire_mins = result.get("lifeTime", 60)

    # Save track_id for polling
    await db.update_deposit_txn(did, track_id)

    await message.answer(
        f"₿ <b>CRYPTO DEPOSIT</b>\n{SEP}\n"
        f"🪙 Currency: <b>{currency} ({network})</b>\n"
        f"💰 Send Exactly: <b>{pay_amount} {currency}</b>\n"
        f"📬 To Address:\n<code>{pay_address}</code>\n"
        f"{SEP}\n"
        f"📊 Rate: $1 = <b>{rate} Tokens</b>\n"
        f"🪙 Gross: <b>{gross_tokens:,.0f}</b> Tokens\n"
        f"🧾 Tax ({dep_tax_pct}%): <b>-{tax_tokens:,.4f}</b>\n"
        f"✅ You Receive: <b>{net_tokens:,.4f} Tokens</b>\n"
        f"{SEP}\n"
        f"⏳ Auto-confirms in ~5 min\n"
        f"⚠️ Send EXACT amount, correct network!\n"
        f"🕐 Expires in <b>{expire_mins} min</b>\n"
        f"🆔 Order: <b>#{did}</b>",
        parse_mode="HTML",
        reply_markup=back_kb()
    )

    user = await db.get_user(user_id)
    uname = user.get("username", str(user_id)) if user else str(user_id)
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"₿ <b>OXAPAY DEPOSIT CREATED</b>\n{SEP}\n"
                f"👤 @{uname} (<code>{user_id}</code>)\n"
                f"💰 {pay_amount} {currency} ({network})\n"
                f"🪙 Net Tokens: {net_tokens:,.4f}\n"
                f"🆔 #{did} | Track: {track_id}",
                parse_mode="HTML"
            )
        except:
            pass

    # Start polling in background
    asyncio.create_task(poll_oxapay_status(bot, track_id, did, user_id, net_tokens))


async def poll_oxapay_status(bot: Bot, track_id: str, did: int, user_id: int, net_tokens: float):
    """Poll Oxapay every 30s for up to 90 minutes."""
    for _ in range(180):
        await asyncio.sleep(30)
        data = await check_payment(track_id)
        if not data:
            continue

        status = data.get("status", "")

        if status in PAID_STATUSES:
            deposit = await db.get_deposit(did)
            if not deposit or deposit["status"] != "pending":
                return

            await db.update_deposit_status(did, "approved", token_credited=net_tokens)
            await db.update_token_balance(user_id, net_tokens)
            await db.add_transaction(user_id, "crypto_deposit", net_tokens, currency="TOKEN")

            try:
                await bot.send_message(
                    user_id,
                    success_text(
                        f"₿ Crypto Payment Confirmed!\n"
                        f"✅ Tokens Credited: <b>{net_tokens:,.4f}</b>"
                    ),
                    parse_mode="HTML"
                )
            except:
                pass

            user = await db.get_user(user_id)
            uname = user.get("username", str(user_id)) if user else str(user_id)
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(
                        admin_id,
                        f"✅ <b>OXAPAY CONFIRMED</b>\n{SEP}\n"
                        f"👤 @{uname} (<code>{user_id}</code>)\n"
                        f"🪙 {net_tokens:,.4f} Tokens credited\n"
                        f"🆔 #{did}",
                        parse_mode="HTML"
                    )
                except:
                    pass
            return

        elif status in FAILED_STATUSES:
            deposit = await db.get_deposit(did)
            if deposit and deposit["status"] == "pending":
                await db.update_deposit_status(did, "rejected")
            try:
                await bot.send_message(
                    user_id,
                    error_text(f"Crypto payment {status}.\nDeposit #{did} cancelled."),
                    parse_mode="HTML"
                )
            except:
                pass
            return


# ─── ADMIN APPROVE/REJECT UPI ──────────────────────────────────────────────────

async def approve_deposit(callback: CallbackQuery, bot: Bot, did: int):
    deposit = await db.get_deposit(did)
    if not deposit:
        await callback.answer("Not found!", show_alert=True); return
    if deposit["status"] != "pending":
        await callback.answer("Already processed!", show_alert=True); return

    user_id = deposit["user_id"]
    method = deposit.get("method", "upi")
    dep_tax_pct = await db.get_effective_deposit_tax(user_id)

    if method == "stars":
        gross, tax, net, dep_tax_pct = await tokens_for_stars(user_id, int(deposit.get("stars_amount", 0)))
    elif method == "upi":
        gross, tax, net, dep_tax_pct = await tokens_for_inr(user_id, float(deposit.get("inr_amount", 0)))
    elif method == "oxapay":
        usd = float(deposit.get("crypto_amount", 0))
        gross, tax, net, dep_tax_pct = await tokens_for_usd(user_id, usd)
    else:
        gross, tax, net = 0, 0, 0

    await db.update_deposit_status(did, "approved", token_credited=net)
    await db.update_token_balance(user_id, net)
    await db.add_transaction(user_id, "deposit", net, currency="TOKEN")

    try:
        await callback.message.edit_caption(
            f"✅ <b>DEPOSIT APPROVED</b> #{did}\n"
            f"🪙 Tokens: {net:,.4f} (Tax: {dep_tax_pct}%)",
            parse_mode="HTML"
        )
    except:
        try:
            await callback.message.edit_text(
                f"✅ <b>DEPOSIT APPROVED</b> #{did}\n🪙 {net:,.4f} Tokens",
                parse_mode="HTML"
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
                f"✅ Credited: <b>{net:,.4f} Tokens</b>"
            ),
            parse_mode="HTML"
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
            parse_mode="HTML"
        )
    except:
        pass
    await callback.answer("❌ Rejected!")
    
