import asyncio
import random
import string
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, PreCheckoutQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_IDS
from database import db
from utils.logger import logger
from utils.decorators import cooldown, registered_only
from utils.helpers import validate_amount, format_balance
from ui.keyboards import (
    main_menu_kb, games_menu_kb, wallet_inr_kb, wallet_crypto_kb,
    deposit_inr_menu_kb, back_to_main_kb, back_kb, coinflip_choice_kb,
    admin_panel_kb, admin_settings_kb, admin_crypto_kb, admin_crypto_detail_kb,
    approve_reject_deposit_kb, approve_reject_withdraw_kb,
    approve_reject_currency_kb, bonus_claim_kb, redeem_menu_kb,
    swap_menu_kb, crypto_withdraw_select_kb, support_reply_kb
)
from ui.messages import (
    main_menu_text, wallet_inr_text, wallet_crypto_text, referral_text,
    game_result_text, history_text, error_text, success_text, SEP
)
from games.dice import play_dice
from games.basketball import play_basketball
from games.soccer import play_soccer
from games.bowling import play_bowling
from games.darts import play_darts
from games.limbo import play_limbo
from games.coinflip import prompt_coinflip, play_coinflip
from payments.deposit import (
    show_deposit_stars, send_stars_invoice,
    start_upi_deposit, start_crypto_deposit,
    approve_deposit, reject_deposit,
    process_stars_payment, handle_successful_payment
)
from payments.withdraw import (
    process_inr_withdrawal, process_crypto_withdrawal,
    approve_withdrawal, reject_withdrawal
)
from admin.panel import (
    show_admin_panel, show_pending_deposits, show_pending_withdrawals,
    show_admin_stats, show_admin_settings, show_crypto_manager,
    show_currency_requests,
    cmd_add_balance, cmd_remove_balance, cmd_set_balance, cmd_broadcast
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ─── FSM ──────────────────────────────────────────────────────────────────────

class DepositFSM(StatesGroup):
    stars_amount = State()
    upi_amount = State()
    upi_screenshot = State()
    upi_txn_id = State()
    crypto_symbol = State()
    crypto_amount = State()
    crypto_screenshot = State()
    crypto_txn_id = State()

class WithdrawFSM(StatesGroup):
    inr_combined = State()
    crypto_symbol = State()
    crypto_amount = State()
    crypto_address = State()

class SupportState(StatesGroup):
    waiting_message = State()

class AdminFSM(StatesGroup):
    waiting_value = State()
    crypto_add_symbol = State()
    crypto_add_name = State()
    crypto_add_network = State()
    crypto_add_address = State()
    crypto_update_address = State()
    support_reply = State()

class RedeemFSM(StatesGroup):
    waiting_code = State()

class SwapFSM(StatesGroup):
    waiting_amount = State()

class GenCodeFSM(StatesGroup):
    waiting_currency = State()
    waiting_amount = State()
    waiting_code_name = State()


# ─── HELPERS ──────────────────────────────────────────────────────────────────

async def get_user_currency(user_id: int) -> str:
    user = await db.get_user(user_id)
    return user.get("currency_mode", "inr") if user else "inr"


async def check_and_process_bonus_eligibility(user_id: int, first_name: str, last_name: str, username: str):
    user = await db.get_user(user_id)
    if not user: return
    tag = await db.get_setting("bot_username_tag") or ""
    if not tag: return
    tag_lower = tag.lower().strip("@")
    full_name = f"{first_name} {last_name or ''}".lower()
    has_tag = tag_lower in full_name or tag_lower in (username or "").lower()
    tag_display = f"@{tag_lower}"

    if has_tag:
        if not user.get("bonus_eligible"):
            await db.set_bonus_eligible(user_id, 1)
            await db.set_warn(user_id, 0, None)
            try:
                await bot.send_message(
                    user_id,
                    f"✅ *BONUS ELIGIBLE!*\n{SEP}\n"
                    f"We found *{tag_display}* in your profile! 🎉\n\n"
                    f"⚠️ Don't remove it — removal resets your progress!\n"
                    f"After adding tag, /start the bot again to verify.",
                    parse_mode="Markdown"
                )
            except: pass
        elif user.get("bonus_warned"):
            await db.set_warn(user_id, 0, None)
            try:
                await bot.send_message(user_id, f"✅ *Tag Restored!* Keep *{tag_display}* in your profile!", parse_mode="Markdown")
            except: pass
    else:
        if user.get("bonus_eligible"):
            if not user.get("bonus_warned"):
                warn_time = (datetime.now() + timedelta(hours=1)).isoformat()
                await db.set_warn(user_id, 1, warn_time)
                try:
                    await bot.send_message(
                        user_id,
                        f"⚠️ *WARNING — Tag Removed!*\n{SEP}\n"
                        f"Add *{tag_display}* to your name.\n"
                        f"⏰ You have *1 hour* or progress resets!",
                        parse_mode="Markdown"
                    )
                except: pass
            else:
                warn_time_str = user.get("warn_time")
                if warn_time_str and datetime.now() > datetime.fromisoformat(warn_time_str):
                    await db.reset_bonus_progress(user_id)
                    try:
                        await bot.send_message(user_id, f"❌ *BONUS RESET*\n{SEP}\nAdd *{tag_display}* back to restart!", parse_mode="Markdown")
                    except: pass


async def can_claim_bonus(user: dict, bonus_type: str) -> bool:
    if not user.get("bonus_eligible"): return False
    try:
        if (datetime.now() - datetime.fromisoformat(user["join_date"])).days < 7: return False
    except: return False
    now = datetime.now()
    if bonus_type == "weekly":
        last = user.get("last_weekly")
        if last and (now - datetime.fromisoformat(last)).days < 7: return False
    else:
        last = user.get("last_monthly")
        if last and (now - datetime.fromisoformat(last)).days < 30: return False
    return True


async def calculate_bonus_amount(user: dict, bonus_type: str) -> float:
    mode = await db.get_setting("bonus_mode") or "fixed"
    if mode == "wagered": return round(user["total_wagered"] * 0.01, 2)
    key = "weekly_bonus" if bonus_type == "weekly" else "monthly_bonus"
    return float(await db.get_setting(key) or "0")


async def pay_referral_bonus(user_id: int, bet_amount: float, currency: str = "INR"):
    user = await db.get_user(user_id)
    if not user or not user.get("referral_id"): return
    ref_pct = float(await db.get_setting("referral_percent") or "1")
    bonus = round(bet_amount * ref_pct / 100, 6)
    if bonus <= 0: return
    referrer_id = user["referral_id"]
    sym = "₹" if currency == "INR" else currency
    if currency == "INR":
        await db.update_referral_earnings(referrer_id, bonus)
    else:
        await db.update_crypto_balance(referrer_id, currency, bonus)
    await db.add_transaction(referrer_id, "referral", bonus, currency=currency)
    try:
        await bot.send_message(
            referrer_id,
            f"🤝 *REFERRAL BONUS!*\n{SEP}\n"
            f"Your referral bet {sym}{bet_amount:,.4f}\n"
            f"💰 You earned: *+{sym}{bonus:.6f}*",
            parse_mode="Markdown"
        )
    except: pass


async def _send_main_menu(target, user_id: int, edit: bool = False):
    user = await db.get_user(user_id)
    is_admin = user_id in ADMIN_IDS
    uname = getattr(target.from_user, 'username', None) or getattr(target.from_user, 'first_name', str(user_id))
    currency_mode = user.get("currency_mode", "inr") if user else "inr"
    crypto_balances = await db.get_all_crypto_balances(user_id) if currency_mode == "crypto" else []
    display = f"@{uname}" if getattr(target.from_user, 'username', None) else uname
    text = main_menu_text(display, user["balance"] if user else 0, currency_mode, crypto_balances)
    kb = main_menu_kb(is_admin=is_admin, currency_mode=currency_mode)
    if edit:
        try:
            await target.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
            return
        except: pass
        await target.message.answer(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await target.answer(text, parse_mode="Markdown", reply_markup=kb)


# ─── GAME HANDLER ─────────────────────────────────────────────────────────────

async def _game_handler(message: Message, game_fn, game_name: str):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        await message.answer("❌ Please /start first."); return

    await check_and_process_bonus_eligibility(
        user_id, message.from_user.first_name or "",
        message.from_user.last_name or "", message.from_user.username or ""
    )

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(f"Usage: `/{game_name} <amount>`", parse_mode="Markdown"); return

    amount, err = validate_amount(parts[1])
    if err:
        await message.answer(error_text(err), parse_mode="Markdown"); return

    currency_mode = user.get("currency_mode", "inr")

    if currency_mode == "inr":
        if user["balance"] < amount:
            await message.answer(error_text(f"Insufficient INR balance!\nYour balance: ₹{user['balance']:,.2f}"), parse_mode="Markdown"); return
    else:
        # For crypto mode, game bets use INR balance too (standard)
        # If you want crypto betting, check crypto balance instead
        if user["balance"] < amount:
            await message.answer(error_text(f"Insufficient balance!\nYour balance: ₹{user['balance']:,.2f}"), parse_mode="Markdown"); return

    if await db.is_balance_locked(user_id):
        await message.answer(error_text("⏳ Game in progress!"), parse_mode="Markdown"); return

    await game_fn(message, bot, amount)
    await pay_referral_bonus(user_id, amount, "INR")


@dp.message(Command("dice"))
@cooldown(3)
@registered_only
async def cmd_dice(message: Message): await _game_handler(message, play_dice, "dice")

@dp.message(Command("bask"))
@cooldown(3)
@registered_only
async def cmd_bask(message: Message): await _game_handler(message, play_basketball, "bask")

@dp.message(Command("ball"))
@cooldown(3)
@registered_only
async def cmd_ball(message: Message): await _game_handler(message, play_soccer, "ball")

@dp.message(Command("bowl"))
@cooldown(3)
@registered_only
async def cmd_bowl(message: Message): await _game_handler(message, play_bowling, "bowl")

@dp.message(Command("darts"))
@cooldown(3)
@registered_only
async def cmd_darts(message: Message): await _game_handler(message, play_darts, "darts")

@dp.message(Command("limbo"))
@cooldown(3)
@registered_only
async def cmd_limbo(message: Message): await _game_handler(message, play_limbo, "limbo")

@dp.message(Command({"coinflip", "cf"}))
@cooldown(3)
@registered_only
async def cmd_cf(message: Message):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: `/cf <amount>`", parse_mode="Markdown"); return
    amount, err = validate_amount(parts[1])
    if err:
        await message.answer(error_text(err), parse_mode="Markdown"); return
    if user["balance"] < amount:
        await message.answer(error_text("Insufficient balance!"), parse_mode="Markdown"); return
    if await db.is_balance_locked(user_id):
        await message.answer(error_text("⏳ Game in progress!"), parse_mode="Markdown"); return
    await prompt_coinflip(message, amount)


# ─── /start ───────────────────────────────────────────────────────────────────

@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or str(user_id)
    last_name = message.from_user.last_name or ""

    args = message.text.split()
    referral_id = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            ref = int(args[1][4:])
            if ref != user_id: referral_id = ref
        except: pass

    existing = await db.get_user(user_id)
    if not existing:
        await db.create_user(user_id, username, referral_id)
        if referral_id:
            try: await bot.send_message(referral_id, f"🎉 New referral!\n👤 {first_name} used your link!")
            except: pass
    else:
        await db.update_username(user_id, username)

    await check_and_process_bonus_eligibility(user_id, first_name, last_name, username)
    await _send_main_menu(message, user_id)


# ─── WALLET ───────────────────────────────────────────────────────────────────

@dp.message(Command("balance"))
@registered_only
async def cmd_balance(message: Message):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    currency_mode = user.get("currency_mode", "inr")
    if currency_mode == "inr":
        await message.answer(wallet_inr_text(user), parse_mode="Markdown", reply_markup=wallet_inr_kb())
    else:
        crypto_bals = await db.get_all_crypto_balances(user_id)
        await message.answer(wallet_crypto_text(user, crypto_bals), parse_mode="Markdown",
                             reply_markup=wallet_crypto_kb(await db.get_all_cryptos()))

@dp.message(Command("withdraw"))
@registered_only
async def cmd_withdraw(message: Message):
    parts = message.text.split()
    if len(parts) >= 3:
        amount, err = validate_amount(parts[1])
        if err:
            await message.answer(error_text(err), parse_mode="Markdown"); return
        await process_inr_withdrawal(message, bot, amount, parts[2])
        return
    await message.answer("💸 INR: `/withdraw <amount> <upi_id>`\nCrypto: use wallet menu", parse_mode="Markdown")

@dp.message(Command("deposit"))
@registered_only
async def cmd_deposit(message: Message):
    user = await db.get_user(message.from_user.id)
    currency_mode = user.get("currency_mode", "inr")
    if currency_mode == "inr":
        await message.answer(f"💳 *DEPOSIT*\n{SEP}\nChoose method:", parse_mode="Markdown", reply_markup=deposit_inr_menu_kb())
    else:
        cryptos = await db.get_all_cryptos()
        await message.answer(f"₿ *CRYPTO DEPOSIT*\n{SEP}\nChoose currency:", parse_mode="Markdown",
                             reply_markup=wallet_crypto_kb(cryptos))


# ─── /tip ─────────────────────────────────────────────────────────────────────

@dp.message(Command("tip"))
@registered_only
async def cmd_tip(message: Message):
    user_id = message.from_user.id
    parts = message.text.split()

    # Group tip: /tip 50 (reply to user) or /tip @username 50
    if message.reply_to_message and len(parts) >= 2:
        amount, err = validate_amount(parts[1])
        if err:
            await message.answer(error_text(err), parse_mode="Markdown"); return
        target_user_id = message.reply_to_message.from_user.id
        target = await db.get_user(target_user_id)
        if not target:
            await message.answer(error_text("That user hasn't used the bot yet."), parse_mode="Markdown"); return
        await _do_tip(message, user_id, target, amount)
        return

    if len(parts) < 3:
        await message.answer(
            f"💸 *TIP*\n{SEP}\n"
            f"Usage:\n"
            f"• `/tip @username 50`\n"
            f"• `/tip user_id 50`\n"
            f"• Reply to a message: `/tip 50`\n"
            f"• In group: `/tip 50` (reply to user)",
            parse_mode="Markdown"
        ); return

    target_raw = parts[1]
    amount, err = validate_amount(parts[2])
    if err:
        await message.answer(error_text(err), parse_mode="Markdown"); return

    target = None
    if target_raw.startswith("@"):
        target = await db.get_user_by_username(target_raw[1:])
    else:
        try: target = await db.get_user(int(target_raw))
        except: target = await db.get_user_by_username(target_raw)

    if not target:
        await message.answer(error_text("User not found. They must have used the bot."), parse_mode="Markdown"); return

    await _do_tip(message, user_id, target, amount)


async def _do_tip(message: Message, sender_id: int, target: dict, amount: float):
    if target["user_id"] == sender_id:
        await message.answer(error_text("Can't tip yourself!"), parse_mode="Markdown"); return

    sender = await db.get_user(sender_id)
    currency_mode = sender.get("currency_mode", "inr")

    if currency_mode == "inr":
        if sender["balance"] < amount:
            await message.answer(error_text(f"Insufficient balance!\nYour balance: ₹{sender['balance']:,.2f}"), parse_mode="Markdown"); return
        await db.update_balance(sender_id, -amount)
        await db.update_balance(target["user_id"], amount)
        await db.add_transaction(sender_id, "tip_sent", amount, currency="INR")
        await db.add_transaction(target["user_id"], "tip_received", amount, currency="INR")
        sym = "₹"
    else:
        # Tip in INR regardless for simplicity (can extend for crypto tip)
        if sender["balance"] < amount:
            await message.answer(error_text(f"Insufficient balance!"), parse_mode="Markdown"); return
        await db.update_balance(sender_id, -amount)
        await db.update_balance(target["user_id"], amount)
        await db.add_transaction(sender_id, "tip_sent", amount, currency="INR")
        await db.add_transaction(target["user_id"], "tip_received", amount, currency="INR")
        sym = "₹"

    sender_name = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
    target_name = f"@{target['username']}" if target.get("username") else str(target["user_id"])

    await message.answer(
        success_text(f"💸 Tip Sent!\n👤 To: {target_name}\n💰 Amount: {sym}{amount:,.2f}"),
        parse_mode="Markdown", reply_markup=back_kb()
    )
    try:
        await bot.send_message(
            target["user_id"],
            f"🎁 *TIP RECEIVED!*\n{SEP}\n👤 From: {sender_name}\n💰 *+{sym}{amount:,.2f}*",
            parse_mode="Markdown"
        )
    except: pass


# ─── /gencode ─────────────────────────────────────────────────────────────────

@dp.message(Command("gencode"))
async def cmd_gencode(message: Message):
    if message.from_user.id not in ADMIN_IDS: return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            f"Usage:\n`/gencode amount` — random code, INR\n"
            f"`/gencode amount MYCODE` — custom code, INR\n"
            f"`/gencode amount CODE USDT` — custom code, crypto",
            parse_mode="Markdown"
        ); return

    amount, err = validate_amount(parts[1])
    if err:
        await message.answer(error_text(err), parse_mode="Markdown"); return

    currency = "INR"
    if len(parts) >= 4:
        currency = parts[3].upper()

    if len(parts) >= 3 and parts[2].upper() != currency:
        code = parts[2].upper()
        existing = await db.get_redeem_code(code)
        if existing:
            await message.answer(error_text(f"Code `{code}` already exists!"), parse_mode="Markdown"); return
    else:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

    await db.create_redeem_code(code, amount, message.from_user.id, currency)
    sym = "₹" if currency == "INR" else currency
    await message.answer(
        success_text(
            f"🎟️ Code Created!\n"
            f"📌 Code: `{code}`\n"
            f"💰 Amount: {sym}{amount:,.4f}\n"
            f"🪙 Currency: {currency}\n"
            f"🔁 Single use only"
        ),
        parse_mode="Markdown"
    )


# ─── /redeem ──────────

@dp.message(Command("redeem"))
@registered_only
async def cmd_redeem(message: Message):
    parts = message.text.split()
    if len(parts) >= 2:
        await _process_redeem(message, parts[1]); return
    await message.answer(
        f"🎟️ *REDEEM CODE*\n{SEP}\nUsage: `/redeem CODE`",
        parse_mode="Markdown", reply_markup=redeem_menu_kb()
    )


async def _process_redeem(message: Message, code: str):
    user_id = message.from_user.id
    code = code.upper().strip()
    record = await db.get_redeem_code(code)
    if not record:
        await message.answer(error_text("Invalid redeem code!"), parse_mode="Markdown", reply_markup=back_kb()); return
    if record["used_by"] is not None:
        await message.answer(error_text("This code has already been used!"), parse_mode="Markdown", reply_markup=back_kb()); return

    success = await db.use_redeem_code(code, user_id)
    if not success:
        await message.answer(error_text("Code already redeemed!"), parse_mode="Markdown", reply_markup=back_kb()); return

    amount = record["amount"]
    currency = record.get("currency", "INR")
    sym = "₹" if currency == "INR" else currency

    if currency == "INR":
        await db.update_balance(user_id, amount)
        await db.add_transaction(user_id, "redeem", amount, currency="INR")
    else:
        await db.update_crypto_balance(user_id, currency, amount)
        await db.add_transaction(user_id, "redeem", amount, currency=currency)

    await message.answer(
        success_text(f"🎟️ Redeemed!\n📌 Code: `{code}`\n💰 Credited: *{sym}{amount:,.4f}*"),
        parse_mode="Markdown", reply_markup=back_kb()
    )


# ─── ADMIN COMMANDS ───────────────────────────────────────────────────────────

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id not in ADMIN_IDS: return
    await show_admin_panel(message)

@dp.message(Command("addbalance"))
async def cmd_addbal(message: Message):
    if message.from_user.id not in ADMIN_IDS: return
    await cmd_add_balance(message, bot)

@dp.message(Command("removebalance"))
async def cmd_removebal(message: Message):
    if message.from_user.id not in ADMIN_IDS: return
    await cmd_remove_balance(message, bot)

@dp.message(Command("setbalance"))
async def cmd_setbal(message: Message):
    if message.from_user.id not in ADMIN_IDS: return
    await cmd_set_balance(message, bot)

@dp.message(Command("broadcast"))
async def cmd_bcast(message: Message):
    if message.from_user.id not in ADMIN_IDS: return
    await cmd_broadcast(message, bot)

@dp.message(Command("reply"))
async def cmd_reply(message: Message):
    if message.from_user.id not in ADMIN_IDS: return
    parts = message.text.split(None, 2)
    if len(parts) < 3:
        await message.answer("Usage: `/reply user_id message`", parse_mode="Markdown"); return
    try:
        await bot.send_message(int(parts[1]), f"💬 *ADMIN REPLY*\n{SEP}\n{parts[2]}", parse_mode="Markdown")
        await message.answer(success_text(f"Reply sent to `{parts[1]}`"), parse_mode="Markdown")
    except Exception as e:
        await message.answer(error_text(str(e)), parse_mode="Markdown")


# ─── SUPPORT ──────────────────────────────────────────────────────────────────

@dp.message(Command("support"))
@registered_only
async def cmd_support(message: Message, state: FSMContext):
    await message.answer("🆘 Send your message:", reply_markup=back_kb())
    await state.set_state(SupportState.waiting_message)

@dp.message(SupportState.waiting_message)
async def support_msg(message: Message, state: FSMContext):
    user_id = message.from_user.id
    uname = message.from_user.username or str(user_id)
    await state.clear()
    ticket_id = await db.create_support_ticket(user_id, message.text or "[media]")
    await message.answer(success_text(f"Message sent! Ticket #{ticket_id}"), parse_mode="Markdown", reply_markup=back_kb())

    for admin_id in ADMIN_IDS:
        try:
            sent = await bot.send_message(
                admin_id,
                f"🆘 *SUPPORT TICKET #{ticket_id}*\n{SEP}\n"
                f"👤 @{uname} (`{user_id}`)\n\n"
                f"{message.text or '[media]'}\n\n"
                f"Reply: `/reply {user_id} msg`",
                parse_mode="Markdown",
                reply_markup=support_reply_kb(ticket_id)
            )
            await db.update_ticket_admin_msg(ticket_id, sent.message_id)
        except: pass


# ─── SUPPORT REPLY CALLBACK ───────────────────────────────────────────────────

@dp.callback_query(F.data.startswith("support_reply_"))
async def cb_support_reply(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Admin only!", show_alert=True); return
    ticket_id = int(callback.data.split("_")[-1])
    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        await callback.answer("Ticket not found!", show_alert=True); return
    await state.set_state(AdminFSM.support_reply)
    await state.update_data(reply_user_id=ticket["user_id"], ticket_id=ticket_id)
    await callback.message.answer(
        f"↩️ Replying to ticket #{ticket_id} (user `{ticket['user_id']}`)\nType your reply:",
        parse_mode="Markdown", reply_markup=back_kb("admin_panel")
    )
    await callback.answer()

@dp.message(AdminFSM.support_reply)
async def admin_support_reply(message: Message, state: FSMContext):
    data = await state.get_data()
    reply_user_id = data.get("reply_user_id")
    ticket_id = data.get("ticket_id")
    await state.clear()
    try:
        await bot.send_message(
            reply_user_id,
            f"💬 *SUPPORT REPLY* (Ticket #{ticket_id})\n{SEP}\n{message.text}",
            parse_mode="Markdown"
        )
        await message.answer(success_text(f"Reply sent to user `{reply_user_id}`"), parse_mode="Markdown")
    except Exception as e:
        await message.answer(error_text(f"Failed: {e}"), parse_mode="Markdown")


# ─── STARS PAYMENT ────────────────────────────────────────────────────────────

@dp.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await process_stars_payment(query, bot)

@dp.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    await handle_successful_payment(message, bot)


# ─── DEPOSIT FSM ──────────────────────────────────────────────────────────────

@dp.message(DepositFSM.stars_amount)
async def deposit_stars_amount(message: Message, state: FSMContext):
    amount, err = validate_amount(message.text)
    if err:
        await message.answer(error_text(err), parse_mode="Markdown"); return
    await state.clear()
    await send_stars_invoice(message, bot, amount)

@dp.message(DepositFSM.upi_amount)
async def deposit_upi_amount(message: Message, state: FSMContext):
    amount, err = validate_amount(message.text)
    if err:
        await message.answer(error_text(err), parse_mode="Markdown"); return
    await state.clear()
    await start_upi_deposit(message, bot, amount)

@dp.message(DepositFSM.crypto_amount)
async def deposit_crypto_amount(message: Message, state: FSMContext):
    amount, err = validate_amount(message.text)
    if err:
        await message.answer(error_text(err), parse_mode="Markdown"); return
    data = await state.get_data()
    symbol = data.get("crypto_symbol")
    await state.clear()
    await start_crypto_deposit(message, bot, symbol, amount)

@dp.callback_query(F.data.startswith("upi_done_"))
async def cb_upi_done(callback: CallbackQuery, state: FSMContext):
    did = int(callback.data.split("_")[-1])
    deposit = await db.get_deposit(did)
    if not deposit or deposit["status"] != "pending":
        await callback.answer("Not found or processed.", show_alert=True); return
    if deposit["user_id"] != callback.from_user.id:
        await callback.answer("Not your request.", show_alert=True); return
    await state.set_state(DepositFSM.upi_screenshot)
    await state.update_data(deposit_id=did)
    try:
        await callback.message.edit_caption(
            (callback.message.caption or "") + "\n\n📸 *Step 1:* Send payment *screenshot*:",
            parse_mode="Markdown"
        )
    except:
        await callback.message.answer("📸 Send your payment screenshot:", parse_mode="Markdown")
    await callback.answer()

@dp.message(DepositFSM.upi_screenshot)
async def deposit_upi_screenshot(message: Message, state: FSMContext):
    if not message.photo:
        await message.answer(error_text("Please send a screenshot PHOTO."), parse_mode="Markdown"); return
    await state.update_data(screenshot_id=message.photo[-1].file_id)
    await state.set_state(DepositFSM.upi_txn_id)
    await message.answer("✅ Screenshot received!\n\n🔖 *Step 2:* Send your *Transaction ID / UTR*:", parse_mode="Markdown")

@dp.message(DepositFSM.upi_txn_id)
async def deposit_upi_txn(message: Message, state: FSMContext):
    txn_id = (message.text or "").strip()
    if not txn_id:
        await message.answer(error_text("Send the Transaction ID.")); return
    data = await state.get_data()
    did = data.get("deposit_id")
    screenshot_id = data.get("screenshot_id", "")
    await state.clear()
    deposit = await db.get_deposit(did)
    if not deposit:
        await message.answer(error_text("Deposit not found.")); return
    await db.update_deposit_screenshot(did, screenshot_id, txn_id)
    user = await db.get_user(message.from_user.id)
    uname = user.get("username", str(message.from_user.id)) if user else str(message.from_user.id)
    dep_tax_pct = float(await db.get_setting("deposit_tax") or "5")
    currency = deposit.get("currency", "INR")
    sym = "₹" if currency == "INR" else currency
    tax = round(deposit["amount"] * dep_tax_pct / 100, 6)
    net = round(deposit["amount"] - tax, 6)
    await message.answer(
        success_text(f"All details received!\n💰 {sym}{deposit['amount']:,.6f}\n🔖 Txn: {txn_id}\n🆔 #{did}\n⏳ Admin verifying..."),
        parse_mode="Markdown", reply_markup=back_kb()
    )
    caption = (
        f"{'🏦 UPI' if currency == 'INR' else '₿ CRYPTO'} *DEPOSIT*\n{SEP}\n"
        f"👤 @{uname} (`{message.from_user.id}`)\n"
        f"💰 {sym}{deposit['amount']:,.6f} | Tax: {dep_tax_pct}% | Net: {sym}{net:,.6f}\n"
        f"🔖 Txn: `{txn_id}`\n🆔 ID: *#{did}*"
    )
    for admin_id in ADMIN_IDS:
        try:
            if screenshot_id:
                await bot.send_photo(admin_id, photo=screenshot_id, caption=caption,
                                     parse_mode="Markdown", reply_markup=approve_reject_deposit_kb(did))
            else:
                await bot.send_message(admin_id, caption, parse_mode="Markdown", reply_markup=approve_reject_deposit_kb(did))
        except Exception as e:
            logger.error(f"Admin notify failed: {e}")

# Crypto deposit also uses same screenshot/txn flow
@dp.message(DepositFSM.crypto_screenshot)
async def deposit_crypto_screenshot(message: Message, state: FSMContext):
    if not message.photo:
        await message.answer(error_text("Please send a screenshot PHOTO."), parse_mode="Markdown"); return
    await state.update_data(screenshot_id=message.photo[-1].file_id)
    await state.set_state(DepositFSM.crypto_txn_id)
    await message.answer("✅ Screenshot received!\n\n🔖 Send your *Transaction Hash / ID*:", parse_mode="Markdown")

@dp.message(DepositFSM.crypto_txn_id)
async def deposit_crypto_txn(message: Message, state: FSMContext):
    # Reuse same logic as UPI txn
    message.text = message.text or ""
    await deposit_upi_txn(message, state)


# ─── WITHDRAW FSM ─────────────────────────────────────────────────────────────

@dp.message(WithdrawFSM.inr_combined)
async def withdraw_inr(message: Message, state: FSMContext):
    parts = (message.text or "").strip().split()
    if len(parts) < 2:
        await message.answer(error_text("Send: `amount upi_id`"), parse_mode="Markdown"); return
    amount, err = validate_amount(parts[0])
    if err:
        await message.answer(error_text(err), parse_mode="Markdown"); return
    await state.clear()
    await process_inr_withdrawal(message, bot, amount, parts[1])

@dp.message(WithdrawFSM.crypto_amount)
async def withdraw_crypto_amount(message: Message, state: FSMContext):
    amount, err = validate_amount(message.text)
    if err:
        await message.answer(error_text(err), parse_mode="Markdown"); return
    await state.update_data(crypto_wd_amount=amount)
    await state.set_state(WithdrawFSM.crypto_address)
    symbol = (await state.get_data()).get("crypto_symbol", "CRYPTO")
    await message.answer(f"📬 Enter your *{symbol}* wallet address:", parse_mode="Markdown")

@dp.message(WithdrawFSM.crypto_address)
async def withdraw_crypto_address(message: Message, state: FSMContext):
    address = (message.text or "").strip()
    if not address:
        await message.answer(error_text("Send a valid wallet address.")); return
    data = await state.get_data()
    symbol = data.get("crypto_symbol")
    amount = data.get("crypto_wd_amount")
    await state.clear()
    await process_crypto_withdrawal(message, bot, symbol, amount, address)


# ─── SWAP FSM ─────────────────────────────────────────────────────────────────

@dp.message(SwapFSM.waiting_amount)
async def swap_amount_received(message: Message, state: FSMContext):
    amount, err = validate_amount(message.text)
    if err:
        await message.answer(error_text(err), parse_mode="Markdown"); return
    data = await state.get_data()
    from_currency = data.get("swap_from")
    to_currency = data.get("swap_to")
    await state.clear()
    await _execute_swap(message, from_currency, to_currency, amount)


async def _execute_swap(message: Message, from_currency: str, to_currency: str, amount: float):
    user_id = message.from_user.id
    swap_fee_pct = float(await db.get_setting("swap_fee_percent") or "1")
    fee = round(amount * swap_fee_pct / 100, 6)
    amount_after_fee = round(amount - fee, 6)

    if from_currency == "INR" and to_currency != "INR":
        # INR → Crypto
        rate = float(await db.get_setting("inr_to_crypto_rate") or "0.012")
        user = await db.get_user(user_id)
        if user["balance"] < amount:
            await message.answer(error_text(f"Insufficient INR balance."), parse_mode="Markdown"); return
        crypto_received = round(amount_after_fee * rate, 6)
        await db.update_balance(user_id, -amount)
        await db.update_crypto_balance(user_id, to_currency, crypto_received)
        await db.add_swap_record(user_id, "INR", to_currency, amount, crypto_received, rate)
        await db.add_transaction(user_id, "swap", amount, currency="INR")
        await message.answer(
            success_text(
                f"🔄 Swap Complete!\n"
                f"₹{amount:,.2f} INR → {crypto_received:.6f} {to_currency}\n"
                f"🧾 Fee ({swap_fee_pct}%): ₹{fee:,.2f}"
            ),
            parse_mode="Markdown", reply_markup=back_kb()
        )
    elif from_currency != "INR" and to_currency == "INR":
        # Crypto → INR
        rate = float(await db.get_setting("crypto_to_inr_rate") or "85")
        bal = await db.get_crypto_balance(user_id, from_currency)
        if bal < amount:
            await message.answer(error_text(f"Insufficient {from_currency} balance.\nYou have: {bal:.6f}"), parse_mode="Markdown"); return
        inr_received = round(amount_after_fee * rate, 2)
        await db.update_crypto_balance(user_id, from_currency, -amount)
        await db.update_balance(user_id, inr_received)
        await db.add_swap_record(user_id, from_currency, "INR", amount, inr_received, rate)
        await db.add_transaction(user_id, "swap", amount, currency=from_currency)
        await message.answer(
            success_text(
                f"🔄 Swap Complete!\n"
                f"{amount:.6f} {from_currency} → ₹{inr_received:,.2f} INR\n"
                f"🧾 Fee ({swap_fee_pct}%): {fee:.6f} {from_currency}"
            ),
            parse_mode="Markdown", reply_markup=back_kb()
        )
    else:
        # Crypto → Crypto
        rate = 1.0
        bal = await db.get_crypto_balance(user_id, from_currency)
        if bal < amount:
            await message.answer(error_text(f"Insufficient {from_currency} balance."), parse_mode="Markdown"); return
        received = amount_after_fee
        await db.update_crypto_balance(user_id, from_currency, -amount)
        await db.update_crypto_balance(user_id, to_currency, received)
        await db.add_swap_record(user_id, from_currency, to_currency, amount, received, rate)
        await message.answer(
            success_text(
                f"🔄 Swap Complete!\n"
                f"{amount:.6f} {from_currency} → {received:.6f} {to_currency}\n"
                f"🧾 Fee ({swap_fee_pct}%): {fee:.6f} {from_currency}"
            ),
            parse_mode="Markdown", reply_markup=back_kb()
        )


# ─── ADMIN SETTINGS FSM ───────────────────────────────────────────────────────

SETTING_PROMPTS = {
    "aset_minwd":           ("min_withdrawal",      "Send new minimum withdrawal amount (₹):"),
    "aset_weekly":          ("weekly_bonus",         "Send new weekly bonus amount (₹):"),
    "aset_monthly":         ("monthly_bonus",        "Send new monthly bonus amount (₹):"),
    "aset_bonusmode":       ("bonus_mode",           "Send: `wagered` or `fixed`"),
    "aset_upi":             ("upi_id",               "Send new UPI ID (e.g. name@upi):"),
    "aset_qr":              ("upi_qr",               "Send UPI QR as PHOTO:"),
    "aset_star":            ("star_payment_id",      "Send Telegram Star Payment token:"),
    "aset_wdtoggle":        ("withdraw_enabled",     "Send `on` or `off`:"),
    "aset_bottag":          ("bot_username_tag",     "Send bot username tag (e.g. @YourBot):"),
    "aset_referral":        ("referral_percent",     "Send referral % (e.g. 1 for 1%):"),
    "aset_deptax":          ("deposit_tax",          "Send deposit tax % (e.g. 5 for 5%):"),
    "aset_wdtax":           ("withdrawal_tax",       "Send withdrawal tax % (e.g. 2 for 2%):"),
    "aset_crypto_inr_rate": ("crypto_to_inr_rate",  "Send crypto→INR rate (e.g. 85 means 1 USDT = ₹85):"),
    "aset_inr_crypto_rate": ("inr_to_crypto_rate",  "Send INR→crypto rate (e.g. 0.012 means ₹1 = 0.012 USDT):"),
    "aset_swap_fee":        ("swap_fee_percent",     "Send swap fee % (e.g. 1 for 1%):"),
}

@dp.message(AdminFSM.waiting_value)
async def admin_setting_value(message: Message, state: FSMContext):
    data = await state.get_data()
    key = data.get("setting_key")
    await state.clear()

    if key == "upi_qr":
        if not message.photo:
            await message.answer(error_text("Send a PHOTO for QR."), parse_mode="Markdown"); return
        await db.set_setting("upi_qr", message.photo[-1].file_id)
        await message.answer(success_text("UPI QR saved!"), parse_mode="Markdown", reply_markup=back_kb("admin_settings")); return

    value = (message.text or "").strip()
    if not value:
        await message.answer(error_text("No text received.")); return

    numeric_keys = ("min_withdrawal", "weekly_bonus", "monthly_bonus", "referral_percent",
                    "deposit_tax", "withdrawal_tax", "crypto_to_inr_rate",
                    "inr_to_crypto_rate", "swap_fee_percent")
    if key in numeric_keys:
        try: float(value)
        except:
            await message.answer(error_text("Invalid number.")); return
    elif key == "withdraw_enabled":
        value = "1" if value.lower() in ("on", "1", "yes") else "0"
    elif key == "bonus_mode":
        if value.lower() not in ("wagered", "fixed"):
            await message.answer(error_text("Send 'wagered' or 'fixed'")); return
        value = value.lower()
    elif key == "bot_username_tag":
        value = value.strip("@").lower()

    await db.set_setting(key, value)
    await message.answer(success_text(f"Updated: `{key}` = `{value}`"), parse_mode="Markdown", reply_markup=back_kb("admin_settings"))


# Crypto add FSM
@dp.message(AdminFSM.crypto_add_symbol)
async def admin_crypto_symbol(message: Message, state: FSMContext):
    symbol = (message.text or "").strip().upper()
    if not symbol:
        await message.answer(error_text("Send symbol e.g. BTC")); return
    await state.update_data(new_crypto_symbol=symbol)
    await state.set_state(AdminFSM.crypto_add_name)
    await message.answer(f"Send full name for *{symbol}* (e.g. Bitcoin):", parse_mode="Markdown")

@dp.message(AdminFSM.crypto_add_name)
async def admin_crypto_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    await state.update_data(new_crypto_name=name)
    await state.set_state(AdminFSM.crypto_add_network)
    await message.answer("Send network name (e.g. TRC20, ERC20, BEP20):")

@dp.message(AdminFSM.crypto_add_network)
async def admin_crypto_network(message: Message, state: FSMContext):
    network = (message.text or "").strip().upper()
    await state.update_data(new_crypto_network=network)
    await state.set_state(AdminFSM.crypto_add_address)
    await message.answer("Send wallet address for deposits:")

@dp.message(AdminFSM.crypto_add_address)
async def admin_crypto_address_new(message: Message, state: FSMContext):
    address = (message.text or "").strip()
    data = await state.get_data()
    await state.clear()
    symbol = data.get("new_crypto_symbol")
    name = data.get("new_crypto_name")
    network = data.get("new_crypto_network")
    await db.add_crypto_currency(symbol, name, network, address)
    await message.answer(
        success_text(f"₿ {symbol} ({network}) added!\nAddress: `{address}`"),
        parse_mode="Markdown", reply_markup=back_kb("admin_crypto")
    )

@dp.message(AdminFSM.crypto_update_address)
async def admin_crypto_update_addr(message: Message, state: FSMContext):
    address = (message.text or "").strip()
    data = await state.get_data()
    symbol = data.get("update_crypto_symbol")
    await state.clear()
    await db.update_crypto_address(symbol, address)
    await message.answer(success_text(f"{symbol} address updated!"), parse_mode="Markdown", reply_markup=back_kb("admin_crypto"))


# ─── REDEEM FSM ───────────────────────────────────────────────────────────────

@dp.message(RedeemFSM.waiting_code)
async def redeem_code_input(message: Message, state: FSMContext):
    await state.clear()
    await _process_redeem(message, (message.text or "").strip())


# ─── CALLBACKS ────────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_main")
async def cb_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _send_main_menu(callback, callback.from_user.id, edit=True)
    await callback.answer()

@dp.callback_query(F.data == "menu_games")
async def cb_games(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.edit_text(
            f"🎮 *GAMES*\n{SEP}\n"
            f"🎲 `/dice <amt>` | 🏀 `/bask <amt>`\n"
            f"⚽ `/ball <amt>` | 🎳 `/bowl <amt>`\n"
            f"🎯 `/darts <amt>` | 🚀 `/limbo <amt>`\n"
            f"🪙 `/cf <amt>` ← Coin Flip",
            parse_mode="Markdown", reply_markup=games_menu_kb()
        )
    except: pass
    await callback.answer()

@dp.callback_query(F.data == "menu_wallet")
async def cb_wallet(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    currency_mode = user.get("currency_mode", "inr") if user else "inr"
    if currency_mode == "inr":
        try:
            await callback.message.edit_text(wallet_inr_text(user), parse_mode="Markdown", reply_markup=wallet_inr_kb())
        except:
            await callback.message.answer(wallet_inr_text(user), parse_mode="Markdown", reply_markup=wallet_inr_kb())
    else:
        crypto_bals = await db.get_all_crypto_balances(user_id)
        cryptos = await db.get_all_cryptos()
        text = wallet_crypto_text(user, crypto_bals)
        try:
            await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=wallet_crypto_kb(cryptos))
        except:
            await callback.message.answer(text, parse_mode="Markdown", reply_markup=wallet_crypto_kb(cryptos))
    await callback.answer()

@dp.callback_query(F.data == "menu_referral")
async def cb_referral(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    bot_info = await bot.get_me()
    ref_count = await db.get_referral_count(callback.from_user.id)
    ref_pct = await db.get_setting("referral_percent") or "1"
    text = referral_text(user, ref_count, bot_info.username)
    text += f"\n💡 Earn *{ref_pct}%* of every bet!"
    try:
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=back_kb())
    except:
        await callback.message.answer(text, parse_mode="Markdown", reply_markup=back_kb())
    await callback.answer()

@dp.callback_query(F.data == "menu_bonus")
async def cb_bonus(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    mode = await db.get_setting("bonus_mode") or "fixed"
    can_weekly = await can_claim_bonus(user, "weekly")
    can_monthly = await can_claim_bonus(user, "monthly")
    if mode == "wagered":
        w_amt = m_amt = round(user["total_wagered"] * 0.01, 2)
    else:
        w_amt = float(await db.get_setting("weekly_bonus") or "0")
        m_amt = float(await db.get_setting("monthly_bonus") or "0")
    try:
        days_old = (datetime.now() - datetime.fromisoformat(user["join_date"])).days
    except: days_old = 0
    tag = await db.get_setting("bot_username_tag") or "not set"
    tag_display = f"@{tag}" if tag and not tag.startswith("@") else tag
    def next_str(last, period):
        if not last: return f"Day {days_old}/{period}" if days_old < period else "Available!"
        diff = (datetime.now() - datetime.fromisoformat(last)).days
        rem = period - diff
        return "Available!" if rem <= 0 else f"In {rem}d"
    text = (
        f"🎁 *BONUS CENTER*\n{SEP}\n"
        f"📊 Status: {'✅ Eligible' if user['bonus_eligible'] else '❌ Not Eligible'}\n"
        f"🏷️ Required: *{tag_display}* in name\n"
        f"🎰 Mode: *{mode}*\n\n"
        f"🗓️ Weekly: *₹{w_amt:,.2f}* — {next_str(user.get('last_weekly'), 7)}\n"
        f"📅 Monthly: *₹{m_amt:,.2f}* — {next_str(user.get('last_monthly'), 30)}\n"
        f"{SEP}\nAdd *{tag_display}* to your name then /start again"
    )
    try:
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=bonus_claim_kb(can_weekly, can_monthly))
    except:
        await callback.message.answer(text, parse_mode="Markdown", reply_markup=bonus_claim_kb(can_weekly, can_monthly))
    await callback.answer()

@dp.callback_query(F.data == "bonus_claim_weekly")
async def cb_weekly(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not await can_claim_bonus(user, "weekly"):
        await callback.answer("Not eligible yet!", show_alert=True); return
    amount = await calculate_bonus_amount(user, "weekly")
    if amount <= 0:
        await callback.answer("Bonus is 0. Contact admin.", show_alert=True); return
    await db.update_balance(callback.from_user.id, amount)
    await db.add_transaction(callback.from_user.id, "deposit", amount, "weekly_bonus", currency="INR")
    await db.update_last_bonus(callback.from_user.id, "weekly")
    await callback.answer(f"✅ ₹{amount:,.2f} weekly bonus credited!", show_alert=True)

@dp.callback_query(F.data == "bonus_claim_monthly")
async def cb_monthly(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not await can_claim_bonus(user, "monthly"):
        await callback.answer("Not eligible yet!", show_alert=True); return
    amount = await calculate_bonus_amount(user, "monthly")
    if amount <= 0:
        await callback.answer("Bonus is 0. Contact admin.", show_alert=True); return
    await db.update_balance(callback.from_user.id, amount)
    await db.add_transaction(callback.from_user.id, "deposit", amount, "monthly_bonus", currency="INR")
    await db.update_last_bonus(callback.from_user.id, "monthly")
    await callback.answer(f"✅ ₹{amount:,.2f} monthly bonus credited!", show_alert=True)

@dp.callback_query(F.data == "menu_support")
async def cb_support(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_text("🆘 Type your message:", reply_markup=back_kb())
    except:
        await callback.message.answer("🆘 Type your message:", reply_markup=back_kb())
    await state.set_state(SupportState.waiting_message)
    await callback.answer()

@dp.callback_query(F.data == "menu_history")
async def cb_history(callback: CallbackQuery):
    txns = await db.get_transactions(callback.from_user.id)
    try:
        await callback.message.edit_text(history_text(txns), parse_mode="Markdown", reply_markup=back_kb())
    except:
        await callback.message.answer(history_text(txns), parse_mode="Markdown", reply_markup=back_kb())
    await callback.answer()

@dp.callback_query(F.data == "menu_redeem")
async def cb_redeem_menu(callback: CallbackQuery):
    try:
        await callback.message.edit_text(
            f"🎟️ *REDEEM CODE*\n{SEP}\nEnter your code to get free balance!\nUse: `/redeem CODE`",
            parse_mode="Markdown", reply_markup=redeem_menu_kb()
        )
    except:
        await callback.message.answer("🎟️ Use `/redeem CODE`", parse_mode="Markdown", reply_markup=redeem_menu_kb())
    await callback.answer()

@dp.callback_query(F.data == "redeem_enter")
async def cb_redeem_enter(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_text("🎟️ Send your redeem code:", reply_markup=back_kb("menu_redeem"))
    except:
        await callback.message.answer("Send your code:", reply_markup=back_kb("menu_redeem"))
    await state.set_state(RedeemFSM.waiting_code)
    await callback.answer()

@dp.callback_query(F.data == "menu_swap")
async def cb_swap(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    currency_mode = user.get("currency_mode", "inr") if user else "inr"
    cryptos = await db.get_all_cryptos()
    swap_fee = await db.get_setting("swap_fee_percent") or "1"
    crypto_inr = await db.get_setting("crypto_to_inr_rate") or "85"
    inr_crypto = await db.get_setting("inr_to_crypto_rate") or "0.012"
    text = (
        f"🔄 *SWAP*\n{SEP}\n"
        f"💱 Crypto→INR Rate: 1 USDT = ₹{crypto_inr}\n"
        f"💱 INR→Crypto Rate: ₹1 = {inr_crypto} USDT\n"
        f"🧾 Swap Fee: *{swap_fee}%*\n{SEP}\nChoose swap direction:"
    )
    try:
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=swap_menu_kb(currency_mode, cryptos))
    except:
        await callback.message.answer(text, parse_mode="Markdown", reply_markup=swap_menu_kb(currency_mode, cryptos))
    await callback.answer()

@dp.callback_query(F.data.startswith("swap_"))
async def cb_swap_select(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    # Format: swap_FROM_to_TO
    try:
        from_cur = parts[1]
        to_cur = parts[3]
    except:
        await callback.answer("Invalid swap.", show_alert=True); return

    await state.set_state(SwapFSM.waiting_amount)
    await state.update_data(swap_from=from_cur, swap_to=to_cur)
    sym_from = "₹" if from_cur == "INR" else from_cur
    try:
        await callback.message.edit_text(
            f"🔄 *SWAP {from_cur} → {to_cur}*\n{SEP}\nEnter amount to swap:",
            parse_mode="Markdown", reply_markup=back_kb("menu_swap")
        )
    except:
        await callback.message.answer(f"Enter {from_cur} amount:", reply_markup=back_kb("menu_swap"))
    await callback.answer()

@dp.callback_query(F.data == "swap_crypto_to_inr")
async def cb_swap_crypto_inr(callback: CallbackQuery, state: FSMContext):
    cryptos = await db.get_all_cryptos()
    if not cryptos:
        await callback.answer("No crypto available.", show_alert=True); return
    if len(cryptos) == 1:
        await state.set_state(SwapFSM.waiting_amount)
        await state.update_data(swap_from=cryptos[0]["symbol"], swap_to="INR")
        try:
            await callback.message.edit_text(
                f"🔄 *SWAP {cryptos[0]['symbol']} → INR*\n{SEP}\nEnter {cryptos[0]['symbol']} amount:",
                parse_mode="Markdown", reply_markup=back_kb("menu_swap")
            )
        except:
            await callback.message.answer(f"Enter {cryptos[0]['symbol']} amount:")
    else:
        # Build selection
        builder_text = f"🔄 Choose crypto to swap to INR:\n{SEP}\n"
        for c in cryptos:
            builder_text += f"• `{c['symbol']}` — tap: /swap_{c['symbol']}_INR\n"
        await callback.message.answer(builder_text, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "menu_switch_currency")
async def cb_switch_currency(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    current = user.get("currency_mode", "inr")
    pending = user.get("currency_change_requested")

    if pending:
        await callback.answer(f"You already have a pending switch to {pending.upper()}. Wait for admin approval.", show_alert=True)
        return

    requested = "crypto" if current == "inr" else "inr"
    await db.request_currency_change(callback.from_user.id, requested)

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🔁 *CURRENCY SWITCH REQUEST*\n{SEP}\n"
                f"👤 @{user.get('username', str(callback.from_user.id))} (`{callback.from_user.id}`)\n"
                f"🔄 {current.upper()} → {requested.upper()}",
                parse_mode="Markdown",
                reply_markup=approve_reject_currency_kb(callback.from_user.id)
            )
        except: pass

    await callback.answer(
        f"✅ Switch request sent to admin!\nCurrent: {current.upper()} → Requested: {requested.upper()}",
        show_alert=True
    )

@dp.callback_query(F.data == "wallet_deposit")
async def cb_deposit_menu(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    currency_mode = user.get("currency_mode", "inr") if user else "inr"
    if currency_mode == "inr":
        try:
            await callback.message.edit_text(f"💳 *DEPOSIT*\n{SEP}\nChoose method:", parse_mode="Markdown", reply_markup=deposit_inr_menu_kb())
        except:
            await callback.message.answer("💳 Choose method:", reply_markup=deposit_inr_menu_kb())
    else:
        cryptos = await db.get_all_cryptos()
        try:
            await callback.message.edit_text(f"₿ *CRYPTO DEPOSIT*\n{SEP}\nChoose currency:", parse_mode="Markdown",
                                             reply_markup=wallet_crypto_kb(cryptos))
        except:
            await callback.message.answer("₿ Choose crypto:", reply_markup=wallet_crypto_kb(cryptos))
    await callback.answer()

@dp.callback_query(F.data.startswith("crypto_deposit_"))
async def cb_crypto_deposit(callback: CallbackQuery, state: FSMContext):
    symbol = callback.data.split("_")[-1]
    crypto = await db.get_crypto(symbol)
    if not crypto:
        await callback.answer("Crypto not found!", show_alert=True); return
    await state.set_state(DepositFSM.crypto_amount)
    await state.update_data(crypto_symbol=symbol)
    dep_tax = await db.get_setting("deposit_tax") or "5"
    try:
        await callback.message.edit_text(
            f"₿ *{symbol} DEPOSIT*\n{SEP}\n"
            f"🌐 Network: *{crypto['network']}*\n"
            f"🧾 Tax: *{dep_tax}%*\n\n"
            f"Enter amount of *{symbol}* to deposit:",
            parse_mode="Markdown", reply_markup=back_kb("menu_wallet")
        )
    except:
        await callback.message.answer(f"Enter {symbol} amount:", reply_markup=back_kb("menu_wallet"))
    await callback.answer()

@dp.callback_query(F.data == "crypto_withdraw")
async def cb_crypto_withdraw_menu(callback: CallbackQuery):
    cryptos = await db.get_all_cryptos()
    try:
        await callback.message.edit_text(
            f"💸 *CRYPTO WITHDRAW*\n{SEP}\nChoose currency:",
            parse_mode="Markdown", reply_markup=crypto_withdraw_select_kb(cryptos)
        )
    except:
        await callback.message.answer("Choose crypto to withdraw:", reply_markup=crypto_withdraw_select_kb(cryptos))
    await callback.answer()

@dp.callback_query(F.data.startswith("crypto_wd_"))
async def cb_crypto_wd_select(callback: CallbackQuery, state: FSMContext):
    symbol = callback.data.split("_")[-1]
    bal = await db.get_crypto_balance(callback.from_user.id, symbol)
    await state.set_state(WithdrawFSM.crypto_amount)
    await state.update_data(crypto_symbol=symbol)
    wd_tax = await db.get_setting("withdrawal_tax") or "0"
    try:
        await callback.message.edit_text(
            f"💸 *{symbol} WITHDRAWAL*\n{SEP}\n"
            f"💰 Your {symbol} balance: *{bal:.6f}*\n"
            f"🧾 Tax: *{wd_tax}%*\n\n"
            f"Enter amount to withdraw:",
            parse_mode="Markdown", reply_markup=back_kb("crypto_withdraw")
        )
    except:
        await callback.message.answer(f"Enter {symbol} amount to withdraw:")
    await callback.answer()

@dp.callback_query(F.data == "wallet_withdraw")
async def cb_withdraw(callback: CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    currency_mode = user.get("currency_mode", "inr") if user else "inr"
    min_wd = await db.get_setting("min_withdrawal")
    wd_tax = await db.get_setting("withdrawal_tax")
    if currency_mode == "inr":
        try:
            await callback.message.edit_text(
                f"💸 *INR WITHDRAW*\n{SEP}\n"
                f"💰 Balance: *₹{user['balance']:,.2f}*\n"
                f"📉 Min: *₹{min_wd}* | Tax: *{wd_tax}%*\n\n"
                f"Send: `amount upi_id`",
                parse_mode="Markdown", reply_markup=back_kb("menu_wallet")
            )
        except:
            await callback.message.answer("Send: `amount upi_id`", parse_mode="Markdown")
        await state.set_state(WithdrawFSM.inr_combined)
    else:
        cryptos = await db.get_all_cryptos()
        try:
            await callback.message.edit_text(
                f"💸 *CRYPTO WITHDRAW*\n{SEP}\nChoose currency:",
                parse_mode="Markdown", reply_markup=crypto_withdraw_select_kb(cryptos)
            )
        except:
            await callback.message.answer("Choose crypto:", reply_markup=crypto_withdraw_select_kb(cryptos))
    await callback.answer()

@dp.callback_query(F.data == "deposit_stars")
async def cb_dep_stars(callback: CallbackQuery, state: FSMContext):
    await show_deposit_stars(callback)
    await state.set_state(DepositFSM.stars_amount)

@dp.callback_query(F.data == "deposit_upi")
async def cb_dep_upi(callback: CallbackQuery, state: FSMContext):
    dep_tax = await db.get_setting("deposit_tax") or "5"
    try:
        await callback.message.edit_text(
            f"🏦 *UPI DEPOSIT*\n{SEP}\n🧾 Tax: *{dep_tax}%*\n\nEnter amount (₹):",
            parse_mode="Markdown", reply_markup=back_kb("wallet_deposit")
        )
    except:
        await callback.message.answer("Enter deposit amount (₹):", reply_markup=back_kb("wallet_deposit"))
    await state.set_state(DepositFSM.upi_amount)
    await callback.answer()

@dp.callback_query(F.data.startswith("dep_approve_"))
async def cb_dep_approve(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Admin only!", show_alert=True); return
    await approve_deposit(callback, bot, int(callback.data.split("_")[-1]))

@dp.callback_query(F.data.startswith("dep_reject_"))
async def cb_dep_reject(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Admin only!", show_alert=True); return
    await reject_deposit(callback, bot, int(callback.data.split("_")[-1]))

@dp.callback_query(F.data.startswith("wd_approve_"))
async def cb_wd_approve(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Admin only!", show_alert=True); return
    await approve_withdrawal(callback, bot, int(callback.data.split("_")[-1]))

@dp.callback_query(F.data.startswith("wd_reject_"))
async def cb_wd_reject(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Admin only!", show_alert=True); return
    await reject_withdrawal(callback, bot, int(callback.data.split("_")[-1]))

@dp.callback_query(F.data.startswith("curr_approve_"))
async def cb_curr_approve(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Admin only!", show_alert=True); return
    user_id = int(callback.data.split("_")[-1])
    new_mode = await db.approve_currency_change(user_id)
    if not new_mode:
        await callback.answer("No pending request.", show_alert=True); return
    try:
        await callback.message.edit_text(f"✅ Currency switch approved for `{user_id}` → *{new_mode.upper()}*", parse_mode="Markdown")
    except: pass
    try:
        await bot.send_message(
            user_id,
            success_text(f"Currency switch approved!\nYou are now in *{new_mode.upper()}* mode."),
            parse_mode="Markdown"
        )
    except: pass
    await callback.answer("✅ Approved!")

@dp.callback_query(F.data.startswith("curr_reject_"))
async def cb_curr_reject(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Admin only!", show_alert=True); return
    user_id = int(callback.data.split("_")[-1])
    await db.request_currency_change(user_id, None)  # clear request (set to NULL)
    # Workaround: directly clear
    import aiosqlite
    async with aiosqlite.connect(db.db_path) as _db:
        await _db.execute("UPDATE users SET currency_change_requested=NULL WHERE user_id=?", (user_id,))
        await _db.commit()
    try:
        await callback.message.edit_text(f"❌ Currency switch rejected for `{user_id}`", parse_mode="Markdown")
    except: pass
    try:
        await bot.send_message(user_id, error_text("Currency switch request was rejected by admin."), parse_mode="Markdown")
    except: pass
    await callback.answer("❌ Rejected!")

@dp.callback_query(F.data == "admin_panel")
async def cb_admin_panel(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Admin only!", show_alert=True); return
    users = await db.get_all_users()
    try:
        await callback.message.edit_text(
            f"🔐 *ADMIN PANEL*\n{SEP}\n👥 Users: *{len(users)}*",
            parse_mode="Markdown", reply_markup=admin_panel_kb()
        )
    except:
        await callback.message.answer(f"🔐 Admin Panel", reply_markup=admin_panel_kb())
    await callback.answer()

@dp.callback_query(F.data == "admin_deposits")
async def cb_adm_deposits(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Admin only!", show_alert=True); return
    await show_pending_deposits(callback)

@dp.callback_query(F.data == "admin_withdrawals")
async def cb_adm_wds(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Admin only!", show_alert=True); return
    await show_pending_withdrawals(callback)

@dp.callback_query(F.data == "admin_stats")
async def cb_adm_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Admin only!", show_alert=True); return
    await show_admin_stats(callback)

@dp.callback_query(F.data == "admin_settings")
async def cb_adm_settings(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Admin only!", show_alert=True); return
    await show_admin_settings(callback)

@dp.callback_query(F.data == "admin_broadcast")
async def cb_adm_broadcast(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Admin only!", show_alert=True); return
    try:
        await callback.message.edit_text("📢 Use: `/broadcast your message`", parse_mode="Markdown", reply_markup=back_kb("admin_panel"))
    except: pass
    await callback.answer()

@dp.callback_query(F.data == "admin_crypto")
async def cb_admin_crypto(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Admin only!", show_alert=True); return
    await show_crypto_manager(callback)

@dp.callback_query(F.data == "admin_currency_requests")
async def cb_admin_currency(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Admin only!", show_alert=True); return
    await show_currency_requests(callback)

@dp.callback_query(F.data == "admin_redeems")
async def cb_adm_redeems(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Admin only!", show_alert=True); return
    codes = await db.get_all_redeem_codes()
    if not codes:
        await callback.message.edit_text(
            f"🎟️ *REDEEM CODES*\n{SEP}\nNo codes yet.\nCreate: `/gencode amount`",
            parse_mode="Markdown", reply_markup=back_kb("admin_panel")
        )
        await callback.answer(); return
    lines = [f"🎟️ *REDEEM CODES*\n{SEP}"]
    for c in codes:
        sym = "₹" if c.get("currency", "INR") == "INR" else c.get("currency", "INR")
        status = f"✅ Used by `{c['used_by']}`" if c["used_by"] else "🟢 Available"
        lines.append(f"`{c['code']}` — {sym}{c['amount']:,.4f} — {status}")
    text = "\n".join(lines)
    if len(text) > 4000: text = text[:4000] + "\n..."
    try:
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=back_kb("admin_panel"))
    except:
        await callback.message.answer(text, parse_mode="Markdown", reply_markup=back_kb("admin_panel"))
    await callback.answer()

@dp.callback_query(F.data.startswith("admin_crypto_detail_"))
async def cb_crypto_detail(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Admin only!", show_alert=True); return
    symbol = callback.data.split("_")[-1]
    crypto = await db.get_crypto(symbol)
    if not crypto:
        await callback.answer("Not found!", show_alert=True); return
    status = "🟢 Enabled" if crypto["enabled"] else "🔴 Disabled"
    try:
        await callback.message.edit_text(
            f"₿ *{symbol} ({crypto['network']})*\n{SEP}\n"
            f"📛 Name: {crypto['name']}\n"
            f"🌐 Network: {crypto['network']}\n"
            f"📬 Address: `{crypto['wallet_address']}`\n"
            f"🔘 Status: {status}",
            parse_mode="Markdown",
            reply_markup=admin_crypto_detail_kb(symbol, crypto["enabled"])
        )
    except:
        await callback.message.answer(f"₿ {symbol}", reply_markup=admin_crypto_detail_kb(symbol, crypto["enabled"]))
    await callback.answer()

@dp.callback_query(F.data.startswith("admin_crypto_toggle_"))
async def cb_crypto_toggle(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Admin only!", show_alert=True); return
    symbol = callback.data.split("_")[-1]
    crypto = await db.get_crypto(symbol)
    if not crypto:
        await callback.answer("Not found!", show_alert=True); return
    new_state = 0 if crypto["enabled"] else 1
    await db.toggle_crypto(symbol, new_state)
    await callback.answer(f"{'🟢 Enabled' if new_state else '🔴 Disabled'} {symbol}", show_alert=True)
    # Refresh
    crypto = await db.get_crypto(symbol)
    try:
        await callback.message.edit_reply_markup(reply_markup=admin_crypto_detail_kb(symbol, crypto["enabled"]))
    except: pass

@dp.callback_query(F.data.startswith("admin_crypto_addr_"))
async def cb_crypto_update_addr(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Admin only!", show_alert=True); return
    symbol = callback.data.split("_")[-1]
    await state.set_state(AdminFSM.crypto_update_address)
    await state.update_data(update_crypto_symbol=symbol)
    try:
        await callback.message.edit_text(
            f"Send new wallet address for *{symbol}*:",
            parse_mode="Markdown", reply_markup=back_kb("admin_crypto")
        )
    except:
        await callback.message.answer(f"Send new address for {symbol}:")
    await callback.answer()

@dp.callback_query(F.data == "admin_crypto_add")
async def cb_crypto_add(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Admin only!", show_alert=True); return
    await state.set_state(AdminFSM.crypto_add_symbol)
    try:
        await callback.message.edit_text(
            f"➕ *ADD NEW CRYPTO*\n{SEP}\nSend the symbol (e.g. BTC, ETH, TRX):",
            parse_mode="Markdown", reply_markup=back_kb("admin_crypto")
        )
    except:
        await callback.message.answer("Send crypto symbol:")
    await callback.answer()

@dp.callback_query(F.data.startswith("aset_"))
async def cb_admin_set(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Admin only!", show_alert=True); return
    key_data = SETTING_PROMPTS.get(callback.data)
    if not key_data:
        await callback.answer(); return
    db_key, prompt = key_data
    await state.set_state(AdminFSM.waiting_value)
    await state.update_data(setting_key=db_key)
    try:
        await callback.message.edit_text(
            f"⚙️ *{db_key.upper()}*\n{SEP}\n{prompt}",
            parse_mode="Markdown", reply_markup=back_kb("admin_settings")
        )
    except:
        await callback.message.answer(prompt, reply_markup=back_kb("admin_settings"))
    await callback.answer()

@dp.callback_query(F.data.startswith("cf_"))
async def cb_cf(callback: CallbackQuery):
    parts = callback.data.split("_")
    choice, amount = parts[1], float(parts[2])
    user = await db.get_user(callback.from_user.id)
    if not user or user["balance"] < amount:
        await callback.answer("❌ Insufficient balance!", show_alert=True); return
    if await db.is_balance_locked(callback.from_user.id):
        await callback.answer("⏳ Game in progress!", show_alert=True); return
    await play_coinflip(callback, bot, amount, choice)
    await pay_referral_bonus(callback.from_user.id, amount, "INR")
    await callback.answer()

@dp.callback_query(F.data.startswith("game_"))
async def cb_game(callback: CallbackQuery):
    cmd = callback.data[5:]
    display = "cf" if cmd == "coinflip" else cmd
    try:
        await callback.message.edit_text(
            f"Use: `/{display} <amount>`\nExample: `/{display} 100`",
            parse_mode="Markdown", reply_markup=back_kb("menu_games")
        )
    except: pass
    await callback.answer()


# ─── FALLBACK ─────────────────────────────────────────────────────────────────

@dp.message()
async def fallback_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state: return
    if not message.text: return
    if message.text.startswith("/"):
        await message.answer("❓ Unknown command. Use /start", reply_markup=back_kb()); return
    user = await db.get_user(message.from_user.id)
    if user:
        await _send_main_menu(message, message.from_user.id)
    else:
        await message.answer("Please use /start to register.")


# ─── STARTUP ──────────────────────────────────────────────────────────────────

async def main():
    await db.init()
    import aiosqlite
    async with aiosqlite.connect(db.db_path) as _db:
        await _db.execute("DELETE FROM balance_locks")
        await _db.commit()
    logger.info("🎰 Casino Bot started!")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
