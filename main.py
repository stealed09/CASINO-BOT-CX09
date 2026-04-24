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
    main_menu_kb, games_menu_kb, wallet_kb,
    deposit_method_kb, back_to_main_kb, back_kb, coinflip_choice_kb,
    admin_panel_kb, admin_settings_kb, admin_crypto_kb, admin_crypto_detail_kb,
    approve_reject_deposit_kb, approve_reject_withdraw_kb,
    bonus_claim_kb, redeem_menu_kb, leaderboard_kb,
    admin_wager_kb, admin_user_action_kb, upi_paid_done_kb,
    withdraw_method_kb, oxapay_currency_kb,
    support_reply_kb
)
from ui.messages import (
    main_menu_text, wallet_text, referral_text, bonus_text,
    game_result_text, history_text, error_text, success_text,
    leaderboard_text, SEP
)
from games.dice import play_dice, play_dice_easy, play_dice_crazy
from games.basketball import play_basketball
from games.soccer import play_soccer
from games.bowling import play_bowling
from games.darts import play_darts
from games.limbo import play_limbo, play_limbo_multiplier
from games.coinflip import prompt_coinflip, play_coinflip
from payments.deposit import (
    show_deposit_stars, send_stars_invoice,
    start_upi_deposit, process_stars_payment, handle_successful_payment,
    approve_deposit, reject_deposit,
    start_oxapay_deposit, create_oxapay_deposit
)
from payments.withdraw import (
    process_upi_withdrawal, process_crypto_withdrawal,
    process_upi_withdrawal_form, process_crypto_withdrawal_form,
    approve_withdrawal, reject_withdrawal
)
from admin.panel import (
    show_admin_panel, show_pending_deposits, show_pending_withdrawals,
    cmd_regencode, cmd_tip_group,
    show_admin_stats, show_admin_settings, show_crypto_manager,
    show_admin_wager, show_wager_by_period, show_user_full_detail,
    show_user_lookup_prompt,
    cmd_add_balance, cmd_remove_balance, cmd_set_balance,
    cmd_broadcast, cmd_tip, cmd_gencode
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ─── FSM ──────────────────────────────────────────────────────────────────────

class DepositFSM(StatesGroup):
    stars_amount = State()
    upi_amount = State()
    upi_screenshot = State()
    upi_txn_id = State()
    nowpayments_token_amount = State()

class WithdrawFSM(StatesGroup):
    upi_amount = State()
    upi_id = State()
    upi_id_confirm = State()
    upi_requestor = State()
    crypto_symbol = State()
    crypto_token_amount = State()
    crypto_address = State()
    crypto_address_confirm = State()
    crypto_requestor = State()

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
    user_lookup = State()
    user_action_amount = State()
    user_action_tax = State()

class RedeemFSM(StatesGroup):
    waiting_code = State()


# ─── SETTING PROMPTS ──────────────────────────────────────────────────────────

SETTING_PROMPTS = {
    "aset_minwd":               ("min_withdrawal_tokens", "Enter minimum withdrawal in <b>Tokens</b> (e.g. 100):"),
    "aset_wdtoggle":            ("withdraw_enabled", "Send <b>1</b> to enable or <b>0</b> to disable withdrawals:"),
    "aset_weekly":              ("weekly_bonus_tokens", "Enter weekly bonus in <b>Tokens</b>:"),
    "aset_monthly":             ("monthly_bonus_tokens", "Enter monthly bonus in <b>Tokens</b>:"),
    "aset_bonusmode":           ("bonus_mode", "Send <b>fixed</b> or <b>wagered</b>:"),
    "aset_bottag":              ("bot_username_tag", "Send the username tag to require (without @):"),
    "aset_upi":                 ("upi_id", "Send new UPI ID:"),
    "aset_qr":                  ("upi_qr", "Send UPI QR image:"),
    "aset_referral":            ("referral_percent", "Enter referral % (e.g. 1 for 1%):"),
    "aset_deptax":              ("deposit_tax", "Enter global deposit tax % (e.g. 10):"),
    "aset_wdtax":               ("withdrawal_tax", "Enter global withdrawal tax % (e.g. 5):"),
    "aset_inr_token_rate":      ("inr_to_token_rate", "Enter INR→Token rate (e.g. 1 means ₹1 = 1 Token):"),
    "aset_stars_token_rate":    ("stars_to_token_rate", "Enter Stars→Token rate (e.g. 1 means 1 Star = 1 Token):"),
    "aset_crypto_rate_USDT":    ("crypto_to_token_rate_USDT", "Enter USDT→Token rate (e.g. 85 means 1 USDT = 85 Tokens):"),
    "aset_crypto_rate_BTC":     ("crypto_to_token_rate_BTC", "Enter BTC→Token rate:"),
    "aset_crypto_rate_ETH":     ("crypto_to_token_rate_ETH", "Enter ETH→Token rate:"),
    "aset_wager_pct_weekly":    ("bonus_wager_percent_weekly", "Enter weekly wager bonus % (e.g. 1 = 1% of weekly wager):"),
    "aset_gametax":             ("game_tax_percent", "Enter game win tax % (e.g. 5 = 5% deducted from every win):"),
    "aset_limbopct":            ("limbo_win_percent", "Enter Limbo win probability % (e.g. 20 = 20% wins, 80% lose):"),
    "aset_wager_pct_monthly":   ("bonus_wager_percent_monthly", "Enter monthly wager bonus % (e.g. 2 = 2% of monthly wager):"),
    "aset_nowpay_toggle":       ("nowpayments_enabled", "Send <b>1</b> to enable or <b>0</b> to disable Auto Crypto:"),
    "aset_oxapay_key":          ("oxapay_merchant_key", "Send your <b>Oxapay Merchant Key</b>:"),
    "aset_usd_token_rate":      ("usd_to_token_rate", "Enter USD→Token rate (e.g. 85 means $1 = 85 Tokens):"),
}


# ─── HELPERS ──────────────────────────────────────────────────────────────────

async def _send_main_menu(message: Message, user_id: int):
    user = await db.get_user(user_id)
    if not user:
        await message.answer("Please use /start to register.")
        return
    is_admin = user_id in ADMIN_IDS
    text = main_menu_text(user.get("username") or str(user_id), user["token_balance"])
    try:
        await message.edit_text(text, parse_mode="HTML", reply_markup=main_menu_kb(is_admin))
    except:
        await message.answer(text, parse_mode="HTML", reply_markup=main_menu_kb(is_admin))


async def check_and_process_bonus_eligibility(user_id: int, first_name: str, last_name: str, username: str):
    user = await db.get_user(user_id)
    if not user: return
    tag = await db.get_setting("bot_username_tag") or ""
    if not tag: return
    tag_lower = tag.lower().strip("@")
    # Check tag in: first name, last name, or Telegram @username
    has_tag = (
        tag_lower in (first_name or "").lower() or
        tag_lower in (last_name or "").lower() or
        tag_lower in (username or "").lower()
    )
    tag_display = tag_lower

    if has_tag:
        if not user.get("bonus_eligible"):
            await db.set_bonus_eligible(user_id, 1)
            await db.set_warn(user_id, 0, None)
            try:
                await bot.send_message(
                    user_id,
                    f"✅ <b>BONUS UNLOCKED!</b>\n{SEP}\n"
                    f"We detected <b>{tag_display}</b> in your profile!\n\n"
                    f"You are now eligible for:\n"
                    f"🗓️ <b>Weekly Bonus</b>\n"
                    f"📅 <b>Monthly Bonus</b>\n\n"
                    f"⚠️ Keep <b>{tag_display}</b> in your last name or bio.\n"
                    f"Removing it will reset your bonus progress to Day 1!",
                    parse_mode="HTML"
                )
            except:
                pass
        elif user.get("bonus_warned"):
            await db.set_warn(user_id, 0, None)
            try:
                await bot.send_message(
                    user_id,
                    f"✅ <b>Tag Restored!</b>\n{SEP}\n"
                    f"<b>{tag_display}</b> is back in your profile.\n"
                    f"Your bonus eligibility has been saved!\n\n"
                    f"⚠️ Always keep it in your last name or bio.",
                    parse_mode="HTML"
                )
            except:
                pass
    else:
        if user.get("bonus_eligible"):
            if not user.get("bonus_warned"):
                warn_time = (datetime.now() + timedelta(hours=1)).isoformat()
                await db.set_warn(user_id, 1, warn_time)
                try:
                    await bot.send_message(
                        user_id,
                        f"⚠️ <b>WARNING — Tag Removed!</b>\n{SEP}\n"
                        f"We can no longer find <b>{tag_display}</b> in your profile!\n\n"
                        f"👉 Add <b>{tag_display}</b> back to your:\n"
                        f"  • Telegram <b>last name</b>, or\n"
                        f"  • Telegram <b>bio</b>\n\n"
                        f"⏰ You have <b>1 hour</b> to restore it.\n"
                        f"If not restored, your bonus progress resets to <b>Day 1</b>!",
                        parse_mode="HTML"
                    )
                except:
                    pass
            else:
                warn_time_str = user.get("warn_time")
                if warn_time_str and datetime.now() > datetime.fromisoformat(warn_time_str):
                    await db.reset_bonus_progress(user_id)
                    try:
                        await bot.send_message(
                            user_id,
                            f"❌ <b>BONUS RESET!</b>\n{SEP}\n"
                            f"Your 1-hour grace period has expired.\n"
                            f"<b>{tag_display}</b> was not found in your profile.\n\n"
                            f"Your bonus progress has reset to <b>Day 1</b>.\n\n"
                            f"👉 Add <b>{tag_display}</b> to your last name or bio\n"
                            f"to start earning bonuses again!",
                            parse_mode="HTML"
                        )
                    except:
                        pass


async def can_claim_bonus(user: dict, bonus_type: str) -> bool:
    if not user.get("bonus_eligible"): return False
    try:
        if (datetime.now() - datetime.fromisoformat(user["join_date"])).days < 7: return False
    except:
        return False
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
    if mode == "wagered":
        pct_key = "bonus_wager_percent_weekly" if bonus_type == "weekly" else "bonus_wager_percent_monthly"
        pct = float(await db.get_setting(pct_key) or "1")
        wager_key = "weekly_wagered" if bonus_type == "weekly" else "monthly_wagered"
        wager = float(user.get(wager_key, 0) or 0)
        return round(wager * pct / 100, 4)
    key = "weekly_bonus_tokens" if bonus_type == "weekly" else "monthly_bonus_tokens"
    return float(await db.get_setting(key) or "0")


async def pay_referral_bonus(user_id: int, bet_amount: float):
    user = await db.get_user(user_id)
    if not user or not user.get("referral_id"): return
    ref_pct = float(await db.get_setting("referral_percent") or "1")
    bonus = round(bet_amount * ref_pct / 100, 6)
    if bonus <= 0: return
    referrer_id = user["referral_id"]
    await db.update_token_balance(referrer_id, bonus)
    await db.update_referral_earnings(referrer_id, bonus)
    await db.add_transaction(referrer_id, "referral", bonus, currency="TOKEN")
    try:
        await bot.send_message(
            referrer_id,
            f"🤝 <b>REFERRAL BONUS!</b>\n{SEP}\n"
            f"Your referral bet {bet_amount:,.4f} Tokens\n"
            f"🪙 You earned: <b>+{bonus:.6f} Tokens</b>",
            parse_mode="HTML"
        )
    except:
        pass


# ─── START ────────────────────────────────────────────────────────────────────

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first = message.from_user.first_name or ""
    last = message.from_user.last_name or ""

    args = message.text.split()
    ref_id = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            ref_id = int(args[1].split("_")[1])
            if ref_id == user_id: ref_id = None
        except:
            ref_id = None

    existed = await db.get_user(user_id)
    await db.create_user(user_id, username, ref_id)
    if not existed and ref_id:
        ref_bonus = float(await db.get_setting("referral_percent") or "1")
        try:
            await bot.send_message(
                ref_id,
                f"🤝 <b>NEW REFERRAL!</b>\n{SEP}\n"
                f"👤 @{username or user_id} joined via your link!\n"
                f"🪙 You'll earn {ref_bonus}% of their bets.",
                parse_mode="HTML"
            )
        except:
            pass

    await db.update_username(user_id, username)
    await check_and_process_bonus_eligibility(user_id, first, last, username)

    user = await db.get_user(user_id)
    is_admin = user_id in ADMIN_IDS
    text = main_menu_text(username or str(user_id), user["token_balance"])
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu_kb(is_admin))


# ─── MAIN MENU NAVIGATION ─────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_main")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Use /start first!", show_alert=True); return
    is_admin = callback.from_user.id in ADMIN_IDS
    text = main_menu_text(user.get("username") or str(callback.from_user.id), user["token_balance"])
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu_kb(is_admin))
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=main_menu_kb(is_admin))
    await callback.answer()


@dp.callback_query(F.data == "menu_games")
async def cb_games(callback: CallbackQuery):
    try:
        await callback.message.edit_text(
            f"🎮 <b>GAMES</b>\n{SEP}\nChoose a game or use commands:",
            parse_mode="HTML", reply_markup=games_menu_kb()
        )
    except:
        await callback.message.answer("🎮 Games:", reply_markup=games_menu_kb())
    await callback.answer()


@dp.callback_query(F.data == "menu_wallet")
async def cb_wallet(callback: CallbackQuery):
    await check_and_process_bonus_eligibility(
        callback.from_user.id,
        callback.from_user.first_name or "",
        callback.from_user.last_name or "",
        callback.from_user.username or ""
    )
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Use /start!", show_alert=True); return
    try:
        await callback.message.edit_text(
            wallet_text(user), parse_mode="HTML", reply_markup=wallet_kb()
        )
    except:
        await callback.message.answer(wallet_text(user), parse_mode="HTML", reply_markup=wallet_kb())
    await callback.answer()


@dp.callback_query(F.data == "menu_referral")
async def cb_referral(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    me = await bot.get_me()
    async with __import__("aiosqlite").connect(db.db_path) as _db:
        async with _db.execute("SELECT COUNT(*) FROM users WHERE referral_id=?", (callback.from_user.id,)) as cur:
            row = await cur.fetchone()
            ref_count = row[0] if row else 0
    try:
        await callback.message.edit_text(
            referral_text(user, ref_count, me.username),
            parse_mode="HTML", reply_markup=back_kb()
        )
    except:
        await callback.message.answer(referral_text(user, ref_count, me.username), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "menu_bonus")
async def cb_bonus(callback: CallbackQuery):
    await check_and_process_bonus_eligibility(
        callback.from_user.id,
        callback.from_user.first_name or "",
        callback.from_user.last_name or "",
        callback.from_user.username or ""
    )
    user = await db.get_user(callback.from_user.id)
    weekly = await db.get_setting("weekly_bonus_tokens") or "0"
    monthly = await db.get_setting("monthly_bonus_tokens") or "0"
    mode = await db.get_setting("bonus_mode") or "fixed"
    tag = (await db.get_setting("bot_username_tag") or "").strip("@").lower()
    can_w = await can_claim_bonus(user, "weekly")
    can_m = await can_claim_bonus(user, "monthly")
    try:
        await callback.message.edit_text(
            bonus_text(user, weekly, monthly, mode, tag),
            parse_mode="HTML", reply_markup=bonus_claim_kb(can_w, can_m)
        )
    except:
        await callback.message.answer(bonus_text(user, weekly, monthly, mode, tag), parse_mode="HTML", reply_markup=bonus_claim_kb(can_w, can_m))
    await callback.answer()


@dp.callback_query(F.data.in_({"bonus_claim_weekly", "bonus_claim_monthly"}))
async def cb_bonus_claim(callback: CallbackQuery):
    bonus_type = "weekly" if "weekly" in callback.data else "monthly"
    user = await db.get_user(callback.from_user.id)
    if not await can_claim_bonus(user, bonus_type):
        await callback.answer("Not eligible or already claimed!", show_alert=True); return
    amount = await calculate_bonus_amount(user, bonus_type)
    if amount <= 0:
        await callback.answer("Bonus amount is 0. Check back later.", show_alert=True); return
    await db.update_token_balance(callback.from_user.id, amount)
    await db.add_transaction(callback.from_user.id, "bonus", amount, currency="TOKEN")
    await db.set_last_bonus(callback.from_user.id, bonus_type)
    await callback.answer(f"✅ {bonus_type.title()} bonus claimed: {amount:,.4f} Tokens!", show_alert=True)
    user = await db.get_user(callback.from_user.id)
    weekly = await db.get_setting("weekly_bonus_tokens") or "0"
    monthly = await db.get_setting("monthly_bonus_tokens") or "0"
    mode = await db.get_setting("bonus_mode") or "fixed"
    tag = (await db.get_setting("bot_username_tag") or "").strip("@").lower()
    can_w = await can_claim_bonus(user, "weekly")
    can_m = await can_claim_bonus(user, "monthly")
    try:
        await callback.message.edit_text(bonus_text(user, weekly, monthly, mode, tag), parse_mode="HTML", reply_markup=bonus_claim_kb(can_w, can_m))
    except:
        pass


@dp.callback_query(F.data == "menu_history")
async def cb_history(callback: CallbackQuery):
    txns = await db.get_transactions(callback.from_user.id, limit=15)
    try:
        await callback.message.edit_text(
            history_text(txns), parse_mode="HTML", reply_markup=back_kb()
        )
    except:
        await callback.message.answer(history_text(txns), parse_mode="HTML", reply_markup=back_kb())
    await callback.answer()


@dp.callback_query(F.data == "menu_support")
async def cb_support(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(SupportState.waiting_message)
    try:
        await callback.message.edit_text(
            f"🆘 <b>SUPPORT</b>\n{SEP}\nDescribe your issue:",
            parse_mode="HTML", reply_markup=back_kb()
        )
    except:
        await callback.message.answer("Describe your issue:", reply_markup=back_kb())


@dp.message(SupportState.waiting_message)
async def msg_support(message: Message, state: FSMContext):
    await state.clear()
    tid = await db.create_support_ticket(message.from_user.id, message.text or "")
    user = await db.get_user(message.from_user.id)
    uname = user.get("username", str(message.from_user.id)) if user else str(message.from_user.id)
    await message.answer(success_text(f"Support ticket #{tid} submitted!\nWe'll respond soon."), parse_mode="HTML", reply_markup=back_kb())
    for admin_id in ADMIN_IDS:
        try:
            sent = await bot.send_message(
                admin_id,
                f"🆘 <b>SUPPORT TICKET #{tid}</b>\n{SEP}\n"
                f"👤 @{uname} (<code>{message.from_user.id}</code>)\n"
                f"💬 {message.text}",
                parse_mode="HTML",
                reply_markup=support_reply_kb(tid)
            )
            await db.set_ticket_admin_msg_id(tid, sent.message_id)
        except:
            pass


@dp.callback_query(F.data.startswith("support_reply_"))
async def cb_support_reply(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Admin only!", show_alert=True); return
    tid = int(callback.data.split("_")[-1])
    await state.set_state(AdminFSM.support_reply)
    await state.update_data(ticket_id=tid)
    await callback.answer()
    try:
        await callback.message.edit_text(f"Send your reply for ticket #{tid}:", reply_markup=back_kb("admin_panel"))
    except:
        await callback.message.answer(f"Send reply for #{tid}:")


@dp.message(AdminFSM.support_reply)
async def msg_admin_support_reply(message: Message, state: FSMContext):
    data = await state.get_data()
    tid = data.get("ticket_id")
    await state.clear()
    ticket = await db.get_ticket(tid)
    if not ticket:
        await message.answer(error_text("Ticket not found."), parse_mode="HTML"); return
    try:
        await bot.send_message(
            ticket["user_id"],
            f"📩 <b>SUPPORT REPLY</b> (Ticket #{tid})\n{SEP}\n{message.text}",
            parse_mode="HTML"
        )
        await message.answer(success_text(f"Reply sent for ticket #{tid}"), parse_mode="HTML")
    except Exception as e:
        await message.answer(error_text(f"Failed: {e}"), parse_mode="HTML")


@dp.callback_query(F.data == "menu_redeem")
async def cb_redeem(callback: CallbackQuery):
    try:
        await callback.message.edit_text(
            f"🎟️ <b>REDEEM CODE</b>\n{SEP}\nEnter a code to get free Tokens!",
            parse_mode="HTML", reply_markup=redeem_menu_kb()
        )
    except:
        await callback.message.answer("Redeem:", reply_markup=redeem_menu_kb())
    await callback.answer()


@dp.callback_query(F.data == "redeem_enter")
async def cb_redeem_enter(callback: CallbackQuery, state: FSMContext):
    await state.set_state(RedeemFSM.waiting_code)
    try:
        await callback.message.edit_text("Send your redeem code:", reply_markup=back_kb("menu_redeem"))
    except:
        await callback.message.answer("Send code:")
    await callback.answer()


@dp.message(RedeemFSM.waiting_code)
async def msg_redeem_code(message: Message, state: FSMContext):
    await state.clear()
    code = message.text.strip().upper()
    result = await db.use_redeem_code(code, message.from_user.id)
    if result is None:
        await message.answer(error_text("Invalid code."), parse_mode="HTML", reply_markup=back_kb("menu_redeem"))
    elif result == -1.0:
        await message.answer(error_text("Code already used."), parse_mode="HTML", reply_markup=back_kb("menu_redeem"))
    else:
        await db.update_token_balance(message.from_user.id, result)
        await db.add_transaction(message.from_user.id, "redeem", result, currency="TOKEN")
        await message.answer(
            success_text(f"🎟️ Code Redeemed!\n🪙 <b>{result:,.4f} Tokens</b> added!"),
            parse_mode="HTML", reply_markup=back_kb()
        )


# ─── LEADERBOARD ──────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_leaderboard")
async def cb_leaderboard(callback: CallbackQuery):
    entries = await db.get_top_wagers("lifetime", 10)
    fake = await db.get_fake_leaderboard()
    text = leaderboard_text(entries, "lifetime", fake)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=leaderboard_kb())
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=leaderboard_kb())
    await callback.answer()


@dp.callback_query(F.data.startswith("lb_"))
async def cb_lb_filter(callback: CallbackQuery):
    period = callback.data.split("_")[1]
    entries = await db.get_top_wagers(period, 10)
    fake = await db.get_fake_leaderboard()
    text = leaderboard_text(entries, period, fake)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=leaderboard_kb())
    except:
        await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


# ─── DEPOSIT FLOW ─────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "wallet_deposit")
async def cb_deposit_menu(callback: CallbackQuery):
    dep_tax = await db.get_effective_deposit_tax(callback.from_user.id)
    inr_rate = await db.get_setting("inr_to_token_rate") or "1"
    stars_rate = await db.get_setting("stars_to_token_rate") or "1"
    try:
        await callback.message.edit_text(
            f"💳 <b>DEPOSIT</b>\n{SEP}\n"
            f"🪙 Token Rates:\n"
            f"  🏦 INR: ₹1 = <b>{inr_rate} Token(s)</b>\n"
            f"  ⭐ Stars: 1★ = <b>{stars_rate} Token(s)</b>\n"
            f"  ₿ Crypto: varies by coin\n"
            f"🧾 Your Deposit Tax: <b>{dep_tax}%</b>\n"
            f"{SEP}\nChoose deposit method:",
            parse_mode="HTML", reply_markup=deposit_method_kb()
        )
    except:
        await callback.message.answer("Choose deposit method:", reply_markup=deposit_method_kb())
    await callback.answer()


@dp.callback_query(F.data == "deposit_stars")
async def cb_dep_stars(callback: CallbackQuery, state: FSMContext):
    await show_deposit_stars(callback)
    await state.set_state(DepositFSM.stars_amount)


@dp.message(DepositFSM.stars_amount)
async def msg_stars_amount(message: Message, state: FSMContext):
    try:
        stars = int(message.text.strip())
        if stars < 1:
            raise ValueError
    except:
        await message.answer(error_text("Enter a valid number of Stars (e.g. 100)"), parse_mode="HTML"); return
    await state.clear()
    await send_stars_invoice(message, bot, stars)


@dp.message(lambda m: m.successful_payment is not None)
async def msg_successful_payment(message: Message):
    await handle_successful_payment(message, bot)


@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await process_stars_payment(pre_checkout_query, bot)


@dp.callback_query(F.data == "deposit_upi")
async def cb_dep_upi(callback: CallbackQuery, state: FSMContext):
    dep_tax = await db.get_effective_deposit_tax(callback.from_user.id)
    inr_rate = await db.get_setting("inr_to_token_rate") or "1"
    try:
        await callback.message.edit_text(
            f"🏦 <b>UPI DEPOSIT</b>\n{SEP}\n"
            f"📊 Rate: ₹1 = <b>{inr_rate} Token(s)</b>\n"
            f"🧾 Tax: <b>{dep_tax}%</b>\n\n"
            f"Enter amount in ₹ to deposit:",
            parse_mode="HTML", reply_markup=back_kb("wallet_deposit")
        )
    except:
        await callback.message.answer("Enter deposit amount (₹):", reply_markup=back_kb("wallet_deposit"))
    await state.set_state(DepositFSM.upi_amount)
    await callback.answer()


@dp.message(DepositFSM.upi_amount)
async def msg_upi_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(",", ""))
        if amount <= 0: raise ValueError
    except:
        await message.answer(error_text("Enter valid amount (e.g. 500)"), parse_mode="HTML"); return
    await state.update_data(upi_inr_amount=amount)
    await state.set_state(DepositFSM.upi_screenshot)
    await start_upi_deposit(message, bot, amount)


@dp.callback_query(F.data.startswith("upi_done_"))
async def cb_upi_done(callback: CallbackQuery, state: FSMContext):
    did = int(callback.data.split("_")[-1])
    await callback.answer()
    await state.update_data(upi_did=did)
    await state.set_state(DepositFSM.upi_screenshot)
    try:
        await callback.message.edit_caption(
            f"📸 <b>UPLOAD SCREENSHOT</b>\n{SEP}\n"
            f"Send payment screenshot for Deposit #{did}:",
            parse_mode="HTML",
            reply_markup=back_kb("wallet_deposit")
        )
    except:
        await callback.message.answer("Send payment screenshot:", reply_markup=back_kb("wallet_deposit"))


@dp.message(DepositFSM.upi_screenshot, F.photo)
async def msg_upi_screenshot(message: Message, state: FSMContext):
    data = await state.get_data()
    did = data.get("upi_did")
    if not did:
        await state.clear(); return
    screenshot_id = message.photo[-1].file_id
    await state.update_data(upi_screenshot_id=screenshot_id)
    await state.set_state(DepositFSM.upi_txn_id)
    await message.answer(
        f"✅ Screenshot received!\nNow send your <b>Transaction ID / UTR number</b>:",
        parse_mode="HTML", reply_markup=back_kb("wallet_deposit")
    )


@dp.message(DepositFSM.upi_txn_id)
async def msg_upi_txn_id(message: Message, state: FSMContext):
    data = await state.get_data()
    did = data.get("upi_did")
    screenshot_id = data.get("upi_screenshot_id", "")
    txn_id = message.text.strip()
    await state.clear()

    deposit = await db.get_deposit(did)
    if not deposit:
        await message.answer(error_text("Deposit not found."), parse_mode="HTML"); return

    await db.update_deposit_screenshot(did, screenshot_id, txn_id)

    user = await db.get_user(message.from_user.id)
    uname = user.get("username", str(message.from_user.id)) if user else str(message.from_user.id)

    await message.answer(
        success_text(
            f"Deposit submitted!\n"
            f"🆔 Deposit #{did}\n"
            f"🔖 Txn ID: {txn_id}\n"
            f"⏳ Admin will review soon."
        ),
        parse_mode="HTML", reply_markup=back_kb()
    )

    for admin_id in ADMIN_IDS:
        try:
            if screenshot_id:
                await bot.send_photo(
                    admin_id,
                    photo=screenshot_id,
                    caption=(
                        f"💳 <b>UPI DEPOSIT REQUEST</b>\n{SEP}\n"
                        f"👤 @{uname} (<code>{message.from_user.id}</code>)\n"
                        f"💵 ₹{deposit.get('inr_amount', 0):,.2f}\n"
                        f"🔖 Txn: {txn_id}\n"
                        f"🆔 #{did}"
                    ),
                    parse_mode="HTML",
                    reply_markup=approve_reject_deposit_kb(did)
                )
            else:
                await bot.send_message(
                    admin_id,
                    f"💳 <b>UPI DEPOSIT</b>\n{SEP}\n"
                    f"👤 @{uname} (<code>{message.from_user.id}</code>)\n"
                    f"💵 ₹{deposit.get('inr_amount', 0):,.2f} | Txn: {txn_id}\n"
                    f"🆔 #{did}",
                    parse_mode="HTML",
                    reply_markup=approve_reject_deposit_kb(did)
                )
        except Exception as e:
            logger.error(f"Admin notify failed: {e}")


# ─── NOWPAYMENTS AUTO CRYPTO DEPOSIT ──────────────────────────────────────────

@dp.callback_query(F.data == "deposit_crypto_auto")
async def cb_crypto_auto(callback: CallbackQuery, state: FSMContext):
    dep_tax = await db.get_effective_deposit_tax(callback.from_user.id)
    rate = await db.get_setting("usd_to_token_rate") or "85"
    try:
        await callback.message.edit_text(
            f"₿ <b>CRYPTO DEPOSIT</b>\n{SEP}\n"
            f"⚡ Powered by <b>Oxapay</b>\n"
            f"📊 Rate: $1 = <b>{rate} Tokens</b>\n"
            f"🧾 Tax: <b>{dep_tax}%</b>\n\n"
            f"Enter token amount you want to buy:\nExample: <code>1000</code>",
            parse_mode="HTML", reply_markup=back_kb("wallet_deposit")
        )
    except:
        await callback.message.answer("Enter token amount:", reply_markup=back_kb("wallet_deposit"))
    await state.set_state(DepositFSM.nowpayments_token_amount)
    await callback.answer()


@dp.message(DepositFSM.nowpayments_token_amount)
async def msg_nowpay_token_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        if amount <= 0: raise ValueError
    except:
        await message.answer(error_text("Enter valid token amount"), parse_mode="HTML"); return
    await state.clear()
    try:
        await message.edit_text(
            f"Choose crypto to pay:",
            reply_markup=oxapay_currency_kb(amount)
        )
    except:
        await message.answer("Choose crypto currency:", reply_markup=oxapay_currency_kb(amount))


@dp.callback_query(F.data.startswith("oxapay_"))
async def cb_oxapay_currency(callback: CallbackQuery):
    # Format: oxapay_{CURRENCY}_{NETWORK}_{token_amount}
    parts = callback.data.split("_")
    # parts: ['oxapay', 'USDT', 'TRC20', '1000'] or ['oxapay', 'BTC', 'BTC', '1000']
    if len(parts) < 4:
        await callback.answer("Invalid data.", show_alert=True); return
    try:
        token_amount = float(parts[-1])
        network = parts[-2]
        currency = parts[-3]
    except:
        await callback.answer("Invalid data.", show_alert=True); return
    await callback.answer()
    try:
        await callback.message.edit_text("⏳ Creating payment...", parse_mode="HTML")
    except:
        pass
    asyncio.create_task(
        create_oxapay_deposit(
            callback.message, bot,
            callback.from_user.id,
            currency, network, token_amount
        )
    )


# ─── DEPOSIT APPROVAL ─────────────────────────────────────────────────────────

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


# ─── WITHDRAWAL FLOW ──────────────────────────────────────────────────────────

@dp.callback_query(F.data == "wallet_withdraw")
async def cb_withdraw_menu(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Use /start!", show_alert=True); return
    wd_tax = await db.get_effective_withdraw_tax(callback.from_user.id)
    min_wd = await db.get_setting("min_withdrawal_tokens") or "100"
    cryptos = await db.get_all_cryptos()
    try:
        await callback.message.edit_text(
            f"💸 <b>WITHDRAW</b>\n{SEP}\n"
            f"🪙 Balance: <b>{user['token_balance']:,.4f} Tokens</b>\n"
            f"📉 Minimum: <b>{min_wd} Tokens</b>\n"
            f"🧾 Your Tax: <b>{wd_tax}%</b>\n"
            f"{SEP}\nChoose withdrawal method:",
            parse_mode="HTML", reply_markup=withdraw_method_kb(cryptos)
        )
    except:
        await callback.message.answer("Choose withdraw method:", reply_markup=withdraw_method_kb(cryptos))
    await callback.answer()


@dp.callback_query(F.data == "withdraw_upi")
async def cb_withdraw_upi(callback: CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    wd_tax = await db.get_effective_withdraw_tax(callback.from_user.id)
    inr_rate = float(await db.get_setting("inr_to_token_rate") or "1")
    min_wd = await db.get_setting("min_withdrawal_tokens") or "100"
    try:
        await callback.message.edit_text(
            f"🏦 <b>UPI WITHDRAWAL</b>\n{SEP}\n"
            f"🪙 Balance: <b>{user['token_balance']:,.4f} Tokens</b>\n"
            f"💵 ≈ ₹{user['token_balance'] / inr_rate:,.2f}\n"
            f"📉 Minimum: <b>{min_wd} Tokens</b>\n"
            f"🧾 Tax: <b>{wd_tax}%</b>\n\n"
            f"Enter <b>token amount</b> to withdraw:",
            parse_mode="HTML", reply_markup=back_kb("wallet_withdraw")
        )
    except:
        await callback.message.answer("Enter token amount:", reply_markup=back_kb("wallet_withdraw"))
    await state.set_state(WithdrawFSM.upi_amount)
    await callback.answer()


@dp.message(WithdrawFSM.upi_amount)
async def msg_withdraw_upi_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(",", ""))
        if amount <= 0: raise ValueError
    except:
        await message.answer(error_text("Enter valid token amount (e.g. 500)"), parse_mode="HTML"); return
    await state.update_data(wd_upi_amount=amount)
    await state.set_state(WithdrawFSM.upi_id)
    await message.answer(f"🏦 Enter your <b>UPI ID</b>:\nExample: <code>name@paytm</code>", parse_mode="HTML", reply_markup=back_kb("wallet_withdraw"))

@dp.message(WithdrawFSM.upi_id)
async def msg_withdraw_upi_id(message: Message, state: FSMContext):
    await state.update_data(wd_upi_id=message.text.strip())
    await state.set_state(WithdrawFSM.upi_id_confirm)
    await message.answer("🔁 Re-enter UPI ID to <b>confirm</b>:", parse_mode="HTML", reply_markup=back_kb("wallet_withdraw"))

@dp.message(WithdrawFSM.upi_id_confirm)
async def msg_withdraw_upi_confirm(message: Message, state: FSMContext):
    await state.update_data(wd_upi_confirm=message.text.strip())
    await state.set_state(WithdrawFSM.upi_requestor)
    await message.answer("📛 Enter your <b>Name</b> (for admin reference):", parse_mode="HTML", reply_markup=back_kb("wallet_withdraw"))

@dp.message(WithdrawFSM.upi_requestor)
async def msg_withdraw_upi_requestor(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    await process_upi_withdrawal_form(
        message, bot,
        data["wd_upi_amount"], data["wd_upi_id"], data["wd_upi_confirm"],
        requestor_name=message.text.strip()
    )


@dp.callback_query(F.data.startswith("withdraw_crypto_"))
async def cb_withdraw_crypto(callback: CallbackQuery, state: FSMContext):
    symbol = callback.data.replace("withdraw_crypto_", "")
    user = await db.get_user(callback.from_user.id)
    wd_tax = await db.get_effective_withdraw_tax(callback.from_user.id)
    rate_key = f"crypto_to_token_rate_{symbol.upper()}"
    rate = float(await db.get_setting(rate_key) or "85")
    min_wd = await db.get_setting("min_withdrawal_tokens") or "100"
    crypto_equiv = round(user["token_balance"] / rate, 6)
    await state.set_state(WithdrawFSM.crypto_token_amount)
    await state.update_data(crypto_symbol=symbol)
    try:
        await callback.message.edit_text(
            f"₿ <b>{symbol} WITHDRAWAL</b>\n{SEP}\n"
            f"🪙 Balance: <b>{user['token_balance']:,.4f} Tokens</b>\n"
            f"₿ ≈ {crypto_equiv:.6f} {symbol}\n"
            f"📉 Minimum: <b>{min_wd} Tokens</b>\n"
            f"🧾 Tax: <b>{wd_tax}%</b>\n\n"
            f"Enter token amount to withdraw:",
            parse_mode="HTML", reply_markup=back_kb("wallet_withdraw")
        )
    except:
        await callback.message.answer(f"Enter token amount:")
    await callback.answer()


@dp.message(WithdrawFSM.crypto_token_amount)
async def msg_withdraw_crypto_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        if amount <= 0: raise ValueError
    except:
        await message.answer(error_text("Enter valid amount"), parse_mode="HTML"); return
    await state.update_data(crypto_wd_amount=amount)
    await state.set_state(WithdrawFSM.crypto_address)
    data = await state.get_data()
    symbol = data.get("crypto_symbol")
    crypto = await db.get_crypto(symbol)
    await message.answer(
        f"📬 Enter your <b>{symbol}</b> wallet address ({crypto['network']}):",
        parse_mode="HTML", reply_markup=back_kb("wallet_withdraw")
    )


@dp.message(WithdrawFSM.crypto_address)
async def msg_withdraw_crypto_address(message: Message, state: FSMContext):
    await state.update_data(crypto_addr=message.text.strip())
    await state.set_state(WithdrawFSM.crypto_address_confirm)
    data = await state.get_data()
    symbol = data.get("crypto_symbol", "")
    await message.answer(f"🔁 Re-enter <b>{symbol}</b> address to confirm:", parse_mode="HTML", reply_markup=back_kb("wallet_withdraw"))

@dp.message(WithdrawFSM.crypto_address_confirm)
async def msg_withdraw_crypto_confirm(message: Message, state: FSMContext):
    await state.update_data(crypto_addr_confirm=message.text.strip())
    await state.set_state(WithdrawFSM.crypto_requestor)
    await message.answer("📛 Enter your <b>Name</b> (for admin reference):", parse_mode="HTML", reply_markup=back_kb("wallet_withdraw"))

@dp.message(WithdrawFSM.crypto_requestor)
async def msg_withdraw_crypto_requestor(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    await process_crypto_withdrawal_form(
        message, bot,
        data["crypto_symbol"], data["crypto_wd_amount"],
        data["crypto_addr"], data["crypto_addr_confirm"],
        requestor_name=message.text.strip()
    )


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


# ─── GAMES ────────────────────────────────────────────────────────────────────

async def _play_game(message: Message, amount: float, play_fn, game_name: str):
    user_id = message.from_user.id
    # Check bonus eligibility on every action
    await check_and_process_bonus_eligibility(
        user_id,
        message.from_user.first_name or "",
        message.from_user.last_name or "",
        message.from_user.username or ""
    )
    user = await db.get_user(user_id)
    if not user:
        await message.answer(error_text("Use /start first."), parse_mode="HTML"); return
    if user.get("is_banned"):
        await message.answer(error_text("Account banned."), parse_mode="HTML"); return
    if user["token_balance"] < amount:
        await message.answer(
            error_text(f"Insufficient Tokens.\nBalance: {user['token_balance']:,.4f}"),
            parse_mode="HTML"
        ); return
    if await db.is_balance_locked(user_id):
        await message.answer(error_text("Game in progress. Wait."), parse_mode="HTML"); return

    await db.lock_balance(user_id, amount)
    try:
        result = await play_fn(message, bot, amount)
        if result is None:
            return
        won, reward, tax = result
        if won:
            await db.update_token_balance(user_id, reward - amount)
        else:
            await db.update_token_balance(user_id, -amount)
        await db.update_wagered(user_id, amount)
        await db.add_transaction(
            user_id, "win" if won else "bet",
            reward if won else amount, currency="TOKEN"
        )
        await pay_referral_bonus(user_id, amount)
    finally:
        await db.unlock_balance(user_id)


@dp.message(Command("dice"))
async def cmd_dice(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: <code>/dice amount</code>\nExample: <code>/dice 100</code>", parse_mode="HTML"); return
    try:
        amount = float(parts[1])
        if amount <= 0: raise ValueError
    except:
        await message.answer(error_text("Invalid amount"), parse_mode="HTML"); return
    await _play_game(message, amount, play_dice, "Dice")


@dp.message(Command("basketball", "bask"))
async def cmd_basketball(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: <code>/basketball amount</code>", parse_mode="HTML"); return
    try:
        amount = float(parts[1])
    except:
        await message.answer(error_text("Invalid amount"), parse_mode="HTML"); return
    await _play_game(message, amount, play_basketball, "Basketball")


@dp.message(Command("soccer", "ball"))
async def cmd_soccer(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: <code>/soccer amount</code>", parse_mode="HTML"); return
    try:
        amount = float(parts[1])
    except:
        await message.answer(error_text("Invalid amount"), parse_mode="HTML"); return
    await _play_game(message, amount, play_soccer, "Soccer")


@dp.message(Command("bowling", "bowl"))
async def cmd_bowling(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: <code>/bowling amount</code>", parse_mode="HTML"); return
    try:
        amount = float(parts[1])
    except:
        await message.answer(error_text("Invalid amount"), parse_mode="HTML"); return
    await _play_game(message, amount, play_bowling, "Bowling")


@dp.message(Command("darts"))
async def cmd_darts(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: <code>/darts amount</code>", parse_mode="HTML"); return
    try:
        amount = float(parts[1])
    except:
        await message.answer(error_text("Invalid amount"), parse_mode="HTML"); return
    await _play_game(message, amount, play_darts, "Darts")


@dp.message(Command("limbo"))
async def cmd_limbo(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: <code>/limbo amount</code>", parse_mode="HTML"); return
    try:
        amount = float(parts[1])
    except:
        await message.answer(error_text("Invalid amount"), parse_mode="HTML"); return
    await _play_game(message, amount, play_limbo, "Limbo")


@dp.message(Command("cf"))
async def cmd_cf(message: Message, state: FSMContext):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: <code>/cf amount</code>", parse_mode="HTML"); return
    try:
        amount = float(parts[1])
        if amount <= 0: raise ValueError
    except:
        await message.answer(error_text("Invalid amount"), parse_mode="HTML"); return
    user = await db.get_user(message.from_user.id)
    if not user or user["token_balance"] < amount:
        await message.answer(error_text("Insufficient Tokens."), parse_mode="HTML"); return
    await prompt_coinflip(message, amount)


@dp.callback_query(F.data.startswith("cf_"))
async def cb_cf(callback: CallbackQuery):
    parts = callback.data.split("_")
    choice, amount = parts[1], float(parts[2])
    user = await db.get_user(callback.from_user.id)
    if not user or user["token_balance"] < amount:
        await callback.answer("❌ Insufficient Tokens!", show_alert=True); return
    if await db.is_balance_locked(callback.from_user.id):
        await callback.answer("⏳ Game in progress!", show_alert=True); return

    await db.lock_balance(callback.from_user.id, amount)
    try:
        result = await play_coinflip(callback, bot, amount, choice)
        if result:
            won, reward, tax = result
            if won:
                await db.update_token_balance(callback.from_user.id, reward - amount)
            else:
                await db.update_token_balance(callback.from_user.id, -amount)
            await db.update_wagered(callback.from_user.id, amount)
            await db.add_transaction(
                callback.from_user.id, "win" if won else "bet",
                reward if won else amount, currency="TOKEN"
            )
            await pay_referral_bonus(callback.from_user.id, amount)
    finally:
        await db.unlock_balance(callback.from_user.id)
    await callback.answer()


@dp.callback_query(F.data.startswith("game_"))
async def cb_game(callback: CallbackQuery):
    cmd = callback.data[5:]
    display = "cf" if cmd == "coinflip" else cmd
    try:
        await callback.message.edit_text(
            f"Use: <code>/{display} <amount></code>\nExample: <code>/{display} 100</code>",
            parse_mode="HTML", reply_markup=back_kb("menu_games")
        )
    except:
        pass
    await callback.answer()


# ─── ADMIN PANEL ──────────────────────────────────────────────────────────────

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await show_admin_panel(message)


@dp.callback_query(F.data == "admin_panel")
async def cb_admin_panel(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Admin only!", show_alert=True); return
    users = await db.get_all_users_admin()
    total_tokens = sum(u.get("token_balance", 0) for u in users)
    try:
        await callback.message.edit_text(
            f"🔐 <b>ADMIN PANEL</b>\n{SEP}\n👥 Users: <b>{len(users)}</b> | 🪙 Tokens: <b>{total_tokens:,.4f}</b>",
            parse_mode="HTML", reply_markup=admin_panel_kb()
        )
    except:
        await callback.message.answer("🔐 Admin Panel", reply_markup=admin_panel_kb())
    await callback.answer()


@dp.callback_query(F.data == "admin_deposits")
async def cb_adm_deposits(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    await show_pending_deposits(callback)


@dp.callback_query(F.data == "admin_withdrawals")
async def cb_adm_wds(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS and not await db.is_sub_admin(callback.from_user.id):
        await callback.answer("No access!", show_alert=True); return
    await show_pending_withdrawals(callback)


@dp.callback_query(F.data == "admin_stats")
async def cb_adm_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    await show_admin_stats(callback)


@dp.callback_query(F.data == "admin_settings")
async def cb_adm_settings(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    await show_admin_settings(callback)


@dp.callback_query(F.data == "admin_crypto")
async def cb_admin_crypto(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    await show_crypto_manager(callback)


@dp.callback_query(F.data == "admin_wager")
async def cb_admin_wager(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    await show_admin_wager(callback)


@dp.callback_query(F.data.startswith("awager_"))
async def cb_adm_wager_period(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    period = callback.data.split("_")[1]
    await show_wager_by_period(callback, period)


@dp.callback_query(F.data == "admin_user_lookup")
async def cb_adm_user_lookup(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await show_user_lookup_prompt(callback, state)
    await state.set_state(AdminFSM.user_lookup)


@dp.message(AdminFSM.user_lookup)
async def msg_user_lookup(message: Message, state: FSMContext):
    await state.clear()
    await show_user_full_detail(message, bot, message.text.strip())


# ─── ADMIN USER ACTIONS (from user detail) ─────────────────────────────────────

@dp.callback_query(F.data.startswith("auser_"))
async def cb_auser_action(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Admin only!", show_alert=True); return
    parts = callback.data.split("_")
    action = parts[1]
    user_id = int(parts[2])

    if action == "ban":
        user = await db.get_user(user_id)
        if not user:
            await callback.answer("User not found!", show_alert=True); return
        new_ban = 0 if user.get("is_banned") else 1
        await db.set_ban(user_id, new_ban)
        status = "BANNED" if new_ban else "UNBANNED"
        await callback.answer(f"User {status}", show_alert=True)
        await show_user_full_detail(callback.message, bot, str(user_id))
        return

    prompt_map = {
        "add": f"Enter tokens to ADD to user <code>{user_id}</code>:",
        "remove": f"Enter tokens to REMOVE from user <code>{user_id}</code>:",
        "set": f"Enter new token balance for user <code>{user_id}</code>:",
        "deptax": f"Enter custom deposit tax % for user <code>{user_id}</code> (or -1 to reset to global):",
        "wdtax": f"Enter custom withdraw tax % for user <code>{user_id}</code> (or -1 to reset to global):",
    }
    if action not in prompt_map:
        await callback.answer(); return

    await state.set_state(AdminFSM.user_action_amount)
    await state.update_data(auser_action=action, auser_target=user_id)
    await callback.answer()
    try:
        await callback.message.edit_text(
            prompt_map[action], parse_mode="HTML",
            reply_markup=back_kb("admin_user_lookup")
        )
    except:
        await callback.message.answer(prompt_map[action])


@dp.message(AdminFSM.user_action_amount)
async def msg_auser_action_value(message: Message, state: FSMContext):
    data = await state.get_data()
    action = data.get("auser_action")
    user_id = data.get("auser_target")
    await state.clear()

    try:
        value = float(message.text.strip())
    except:
        await message.answer(error_text("Invalid number."), parse_mode="HTML"); return

    user = await db.get_user(user_id)
    if not user:
        await message.answer(error_text("User not found."), parse_mode="HTML"); return

    if action == "add":
        await db.update_token_balance(user_id, value)
        await db.add_transaction(user_id, "admin_credit", value, "admin", currency="TOKEN")
        await message.answer(success_text(f"Added {value:,.4f} Tokens to <code>{user_id}</code>"), parse_mode="HTML")
        try:
            await bot.send_message(user_id, success_text(f"👑 Admin added <b>{value:,.4f} Tokens</b>!"), parse_mode="HTML")
        except:
            pass
    elif action == "remove":
        if user["token_balance"] < value:
            await message.answer(error_text("Insufficient balance."), parse_mode="HTML"); return
        await db.update_token_balance(user_id, -value)
        await db.add_transaction(user_id, "admin_debit", value, "admin", currency="TOKEN")
        await message.answer(success_text(f"Removed {value:,.4f} Tokens from <code>{user_id}</code>"), parse_mode="HTML")
    elif action == "set":
        await db.set_token_balance(user_id, value)
        await message.answer(success_text(f"Set <code>{user_id}</code> balance to {value:,.4f} Tokens"), parse_mode="HTML")
    elif action == "deptax":
        await db.set_user_custom_tax(user_id, deposit_tax=value)
        await message.answer(success_text(f"Deposit tax for <code>{user_id}</code> set to {value}%"), parse_mode="HTML")
    elif action == "wdtax":
        await db.set_user_custom_tax(user_id, withdraw_tax=value)
        await message.answer(success_text(f"Withdraw tax for <code>{user_id}</code> set to {value}%"), parse_mode="HTML")


# ─── ADMIN SETTINGS ──────────────────────────────────────────────────────────

@dp.callback_query(F.data == "admin_tip_btn")
async def cb_admin_tip_btn(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS and not await db.is_sub_admin(callback.from_user.id):
        await callback.answer("Admin only!", show_alert=True); return
    try:
        await callback.message.edit_text(
            f"💡 <b>TIP USER</b>\n{SEP}\nUse: <code>/tip @username amount</code>\nOr: <code>/tip user_id amount</code>",
            parse_mode="HTML", reply_markup=back_kb("admin_panel")
        )
    except: pass
    await callback.answer()


@dp.callback_query(F.data == "admin_broadcast")
async def cb_adm_broadcast(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    try:
        await callback.message.edit_text(
            "📢 Use: <code>/broadcast your message</code>", parse_mode="HTML",
            reply_markup=back_kb("admin_panel")
        )
    except:
        pass
    await callback.answer()


@dp.callback_query(F.data == "admin_redeems")
async def cb_adm_redeems(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    codes = await db.get_all_redeem_codes()
    if not codes:
        await callback.message.edit_text(
            f"🎟️ <b>REDEEM CODES</b>\n{SEP}\nNo codes yet.\nCreate: <code>/gencode amount [name]</code>",
            parse_mode="HTML", reply_markup=back_kb("admin_panel")
        )
        await callback.answer(); return
    lines = [f"🎟️ <b>REDEEM CODES</b>\n{SEP}"]
    for c in codes:
        status = f"✅ Used by <code>{c['used_by']}</code>" if c["used_by"] else "🟢 Available"
        lines.append(f"<code>{c['code']}</code> — {c['token_amount']:,.4f} T — {status}")
    text = "\n".join(lines)
    if len(text) > 4000: text = text[:4000] + "\n..."
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_kb("admin_panel"))
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=back_kb("admin_panel"))
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
            f"⚙️ <b>{db_key.upper()}</b>\n{SEP}\n{prompt}",
            parse_mode="HTML", reply_markup=back_kb("admin_settings")
        )
    except:
        await callback.message.answer(prompt, reply_markup=back_kb("admin_settings"))
    await callback.answer()


@dp.message(AdminFSM.waiting_value)
async def msg_admin_setting(message: Message, state: FSMContext):
    data = await state.get_data()
    key = data.get("setting_key")
    await state.clear()
    if not key:
        return
    if key == "upi_qr":
        if message.photo:
            val = message.photo[-1].file_id
        else:
            val = message.text.strip()
    else:
        val = message.text.strip()
    await db.set_setting(key, val)
    await message.answer(
        success_text(f"<b>{key}</b> updated to:\n<code>{val}</code>"),
        parse_mode="HTML", reply_markup=back_kb("admin_settings")
    )


# ─── ADMIN CRYPTO MANAGER ─────────────────────────────────────────────────────

@dp.callback_query(F.data.startswith("admin_crypto_detail_"))
async def cb_crypto_detail(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    symbol = callback.data.split("_")[-1]
    crypto = await db.get_crypto(symbol)
    if not crypto:
        await callback.answer("Not found!", show_alert=True); return
    status = "🟢 Enabled" if crypto["enabled"] else "🔴 Disabled"
    try:
        await callback.message.edit_text(
            f"₿ <b>{symbol} ({crypto['network']})</b>\n{SEP}\n"
            f"📛 Name: {crypto['name']}\n"
            f"🌐 Network: {crypto['network']}\n"
            f"📬 Address: <code>{crypto['wallet_address']}</code>\n"
            f"🔘 Status: {status}",
            parse_mode="HTML", reply_markup=admin_crypto_detail_kb(symbol, crypto["enabled"])
        )
    except:
        await callback.message.answer(f"₿ {symbol}", reply_markup=admin_crypto_detail_kb(symbol, crypto["enabled"]))
    await callback.answer()


@dp.callback_query(F.data.startswith("admin_crypto_toggle_"))
async def cb_crypto_toggle(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    symbol = callback.data.split("_")[-1]
    crypto = await db.get_crypto(symbol)
    if not crypto:
        await callback.answer("Not found!", show_alert=True); return
    new_state = 0 if crypto["enabled"] else 1
    await db.toggle_crypto(symbol, new_state)
    await callback.answer(f"{'🟢 Enabled' if new_state else '🔴 Disabled'} {symbol}", show_alert=True)
    crypto = await db.get_crypto(symbol)
    try:
        await callback.message.edit_reply_markup(reply_markup=admin_crypto_detail_kb(symbol, crypto["enabled"]))
    except:
        pass


@dp.callback_query(F.data.startswith("admin_crypto_addr_"))
async def cb_crypto_update_addr(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    symbol = callback.data.split("_")[-1]
    await state.set_state(AdminFSM.crypto_update_address)
    await state.update_data(update_crypto_symbol=symbol)
    try:
        await callback.message.edit_text(
            f"Send new wallet address for <b>{symbol}</b>:",
            parse_mode="HTML", reply_markup=back_kb("admin_crypto")
        )
    except:
        await callback.message.answer(f"Send new address for {symbol}:")
    await callback.answer()


@dp.message(AdminFSM.crypto_update_address)
async def msg_crypto_addr_update(message: Message, state: FSMContext):
    data = await state.get_data()
    symbol = data.get("update_crypto_symbol")
    await state.clear()
    await db.update_crypto_address(symbol, message.text.strip())
    await message.answer(
        success_text(f"<b>{symbol}</b> address updated to:\n<code>{message.text.strip()}</code>"),
        parse_mode="HTML", reply_markup=back_kb("admin_crypto")
    )


@dp.callback_query(F.data == "admin_crypto_add")
async def cb_crypto_add(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await state.set_state(AdminFSM.crypto_add_symbol)
    try:
        await callback.message.edit_text(
            f"➕ <b>ADD CRYPTO</b>\n{SEP}\nSend symbol (e.g. BTC, ETH, TRX):",
            parse_mode="HTML", reply_markup=back_kb("admin_crypto")
        )
    except:
        await callback.message.answer("Send symbol:")
    await callback.answer()


@dp.message(AdminFSM.crypto_add_symbol)
async def msg_crypto_add_sym(message: Message, state: FSMContext):
    await state.update_data(new_crypto_symbol=message.text.strip().upper())
    await state.set_state(AdminFSM.crypto_add_name)
    await message.answer("Send full name (e.g. Bitcoin):")


@dp.message(AdminFSM.crypto_add_name)
async def msg_crypto_add_name(message: Message, state: FSMContext):
    await state.update_data(new_crypto_name=message.text.strip())
    await state.set_state(AdminFSM.crypto_add_network)
    await message.answer("Send network (e.g. TRC20, ERC20, BEP20):")


@dp.message(AdminFSM.crypto_add_network)
async def msg_crypto_add_network(message: Message, state: FSMContext):
    await state.update_data(new_crypto_network=message.text.strip())
    await state.set_state(AdminFSM.crypto_add_address)
    await message.answer("Send wallet address:")


@dp.message(AdminFSM.crypto_add_address)
async def msg_crypto_add_address(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    sym = data["new_crypto_symbol"]
    name = data["new_crypto_name"]
    network = data["new_crypto_network"]
    address = message.text.strip()
    await db.add_crypto(sym, name, network, address)
    await message.answer(
        success_text(f"Added <b>{sym}</b> ({network})\nAddress: <code>{address}</code>"),
        parse_mode="HTML", reply_markup=back_kb("admin_crypto")
    )


# ─── ADMIN COMMANDS ───────────────────────────────────────────────────────────

@dp.message(Command("addbalance"))
async def cmd_add_bal(message: Message):
    if message.from_user.id not in ADMIN_IDS: return
    await cmd_add_balance(message, bot)


@dp.message(Command("removebalance"))
async def cmd_remove_bal(message: Message):
    if message.from_user.id not in ADMIN_IDS: return
    await cmd_remove_balance(message, bot)


@dp.message(Command("setbalance"))
async def cmd_set_bal(message: Message):
    if message.from_user.id not in ADMIN_IDS: return
    await cmd_set_balance(message, bot)


@dp.message(Command("broadcast"))
async def cmd_bc(message: Message):
    if message.from_user.id not in ADMIN_IDS: return
    await cmd_broadcast(message, bot)


@dp.message(Command("tip"))
async def cmd_tip_cmd(message: Message):
    if message.from_user.id not in ADMIN_IDS and not await db.is_sub_admin(message.from_user.id):
        return
    await cmd_tip(message, bot)


@dp.message(Command("gencode"))
async def cmd_gencode_cmd(message: Message):
    if message.from_user.id not in ADMIN_IDS and not await db.is_sub_admin(message.from_user.id):
        return
    await cmd_gencode(message, bot)


@dp.message(Command("regencode"))
async def cmd_regencode_cmd(message: Message):
    if message.from_user.id not in ADMIN_IDS and not await db.is_sub_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: <code>/regencode OLD_CODE</code>", parse_mode="HTML"); return
    await cmd_regencode(message, bot, parts[1].upper())


# Group tip: works if admin/sub-admin mentions in group
@dp.message(F.text.startswith("/tip"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_tip_group_handler(message: Message):
    if message.from_user.id not in ADMIN_IDS and not await db.is_sub_admin(message.from_user.id):
        return
    await cmd_tip_group(message, bot)


@dp.message(Command("userinfo"))
async def cmd_userinfo(message: Message):
    if message.from_user.id not in ADMIN_IDS: return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: <code>/userinfo user_id_or_@username</code>", parse_mode="HTML"); return
    await show_user_full_detail(message, bot, parts[1])


# ─── DICE MODE CALLBACKS ──────────────────────────────────────────────────────

@dp.callback_query(F.data.startswith("dice_easy_"))
async def cb_dice_easy(callback: CallbackQuery):
    try:
        bet = float(callback.data.split("dice_easy_")[1])
    except:
        await callback.answer("Invalid bet", show_alert=True); return
    user = await db.get_user(callback.from_user.id)
    if not user or user["token_balance"] < bet:
        await callback.answer("❌ Insufficient Tokens!", show_alert=True); return
    if await db.is_balance_locked(callback.from_user.id):
        await callback.answer("⏳ Game in progress!", show_alert=True); return
    await check_and_process_bonus_eligibility(
        callback.from_user.id, callback.from_user.first_name or "",
        callback.from_user.last_name or "", callback.from_user.username or ""
    )
    await play_dice_easy(callback, bot, bet)
    await db.update_wagered(callback.from_user.id, bet)
    await pay_referral_bonus(callback.from_user.id, bet)
    await callback.answer()


@dp.callback_query(F.data.startswith("dice_crazy_"))
async def cb_dice_crazy(callback: CallbackQuery):
    try:
        bet = float(callback.data.split("dice_crazy_")[1])
    except:
        await callback.answer("Invalid bet", show_alert=True); return
    user = await db.get_user(callback.from_user.id)
    if not user or user["token_balance"] < bet:
        await callback.answer("❌ Insufficient Tokens!", show_alert=True); return
    if await db.is_balance_locked(callback.from_user.id):
        await callback.answer("⏳ Game in progress!", show_alert=True); return
    await check_and_process_bonus_eligibility(
        callback.from_user.id, callback.from_user.first_name or "",
        callback.from_user.last_name or "", callback.from_user.username or ""
    )
    await play_dice_crazy(callback, bot, bet)
    await pay_referral_bonus(callback.from_user.id, bet)
    await callback.answer()


# ─── LIMBO MULTIPLIER CALLBACKS ───────────────────────────────────────────────

@dp.callback_query(F.data.startswith("limbo_mult_"))
async def cb_limbo_mult(callback: CallbackQuery):
    try:
        parts = callback.data.split("_")
        # limbo_mult_{bet}_{multiplier}
        multiplier = int(parts[-1])
        bet = float(parts[-2])
    except:
        await callback.answer("Invalid data", show_alert=True); return
    user = await db.get_user(callback.from_user.id)
    if not user or user["token_balance"] < bet:
        await callback.answer("❌ Insufficient Tokens!", show_alert=True); return
    if await db.is_balance_locked(callback.from_user.id):
        await callback.answer("⏳ Game in progress!", show_alert=True); return
    await check_and_process_bonus_eligibility(
        callback.from_user.id, callback.from_user.first_name or "",
        callback.from_user.last_name or "", callback.from_user.username or ""
    )
    await play_limbo_multiplier(callback, bot, bet, multiplier)
    await pay_referral_bonus(callback.from_user.id, bet)
    await callback.answer()


# ─── HELP COMMAND ─────────────────────────────────────────────────────────────

@dp.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        f"📖 <b>GAME RULES & HELP</b>\n{SEP}\n"
        f"<b>🎲 DICE</b>\n"
        f"  😊 Easy: /dice amount → Roll ≥4 = WIN (1.9x payout)\n"
        f"  🔥 Crazy: Bot rolls, then you roll — beat bot = WIN (2x)\n\n"
        f"<b>🚀 LIMBO</b>\n"
        f"  /limbo amount → Pick multiplier (2x–100x)\n"
        f"  Rocket must reach your target to win!\n"
        f"  Higher multiplier = bigger payout, lower win chance\n\n"
        f"<b>🪙 COIN FLIP</b>\n"
        f"  /cf amount → Pick 🪙Heads or 🦅Tails — 50/50 (1.9x)\n\n"
        f"<b>🏀 BASKETBALL</b>  /basketball amount\n"
        f"<b>⚽ SOCCER</b>       /soccer amount\n"
        f"<b>🎳 BOWLING</b>      /bowling amount\n"
        f"<b>🎯 DARTS</b>        /darts amount\n\n"
        f"{SEP}\n"
        f"<b>💸 WITHDRAWAL</b>\n"
        f"  Wallet → Withdraw → Choose UPI or Crypto\n"
        f"  Fill form, confirm address twice, submit\n"
        f"  Admin approves/rejects manually\n\n"
        f"<b>🎁 BONUS</b>\n"
        f"  Set bot username in your bio/last name for 7 days → Weekly Bonus\n"
        f"  Stay active monthly → Monthly Bonus\n\n"
        f"<b>🎟️ REDEEM CODE</b>\n"
        f"  Menu → Redeem Code → Enter code\n\n"
        f"<b>🏆 LEADERBOARD</b>\n"
        f"  Shows top wagerers. Compete to reach the top!\n\n"
        f"{SEP}\n"
        f"⚠️ All wins have a small tax deducted (set by admin)\n"
        f"🆘 Issues? Use Support in main menu"
    )
    await message.answer(help_text, parse_mode="HTML", reply_markup=back_kb())


# ─── SUB-ADMIN SYSTEM ─────────────────────────────────────────────────────────

async def is_admin_or_sub(user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    return await db.is_sub_admin(user_id)


@dp.callback_query(F.data == "admin_sub_admins")
async def cb_sub_admins(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Main admin only!", show_alert=True); return
    subs = await db.get_all_sub_admins()
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Add Sub-Admin", callback_data="admin_sub_add"))
    for s in subs:
        builder.row(InlineKeyboardButton(
            text=f"❌ Remove @{s['username'] or s['user_id']}",
            callback_data=f"admin_sub_remove_{s['user_id']}"
        ))
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="admin_panel"))
    lines = [f"👮 <b>SUB ADMINS</b>\n{SEP}"]
    for s in subs:
        lines.append(f"• @{s['username'] or 'unknown'} (<code>{s['user_id']}</code>)")
    if not subs:
        lines.append("No sub-admins yet.")
    try:
        await callback.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=builder.as_markup())
    except:
        await callback.message.answer("\n".join(lines), parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


class SubAdminFSM(StatesGroup):
    waiting_user_id = State()


@dp.callback_query(F.data == "admin_sub_add")
async def cb_sub_add(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Main admin only!", show_alert=True); return
    await state.set_state(SubAdminFSM.waiting_user_id)
    try:
        await callback.message.edit_text(
            f"Send <b>user_id</b> to make sub-admin:\n(They can: tip, create redeem codes, approve withdrawals, view wager)",
            parse_mode="HTML", reply_markup=back_kb("admin_sub_admins")
        )
    except:
        await callback.message.answer("Send user_id:")
    await callback.answer()


@dp.message(SubAdminFSM.waiting_user_id)
async def msg_sub_add(message: Message, state: FSMContext):
    await state.clear()
    try:
        uid = int(message.text.strip())
    except:
        await message.answer(error_text("Invalid user ID"), parse_mode="HTML"); return
    user = await db.get_user(uid)
    uname = user.get("username", "") if user else ""
    await db.add_sub_admin(uid, uname, message.from_user.id)
    await message.answer(
        success_text(f"✅ Sub-admin added: <code>{uid}</code> @{uname}"),
        parse_mode="HTML", reply_markup=back_kb("admin_sub_admins")
    )
    try:
        await bot.send_message(uid, f"👮 <b>You have been made a Sub-Admin!</b>\n{SEP}\nYou can now: tip users, create redeem codes, approve/reject withdrawals.", parse_mode="HTML")
    except: pass


@dp.callback_query(F.data.startswith("admin_sub_remove_"))
async def cb_sub_remove(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Main admin only!", show_alert=True); return
    uid = int(callback.data.split("_")[-1])
    await db.remove_sub_admin(uid)
    await callback.answer("✅ Sub-admin removed!", show_alert=True)
    subs = await db.get_all_sub_admins()
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Add Sub-Admin", callback_data="admin_sub_add"))
    for s in subs:
        builder.row(InlineKeyboardButton(
            text=f"❌ Remove @{s['username'] or s['user_id']}",
            callback_data=f"admin_sub_remove_{s['user_id']}"
        ))
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="admin_panel"))
    try:
        await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
    except: pass


# ─── FAKE LEADERBOARD ADMIN ───────────────────────────────────────────────────

@dp.callback_query(F.data == "admin_fake_lb")
async def cb_fake_lb(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Admin only!", show_alert=True); return
    entries = await db.get_fake_leaderboard()
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Add Fake Entry", callback_data="fake_lb_add"))
    for e in entries:
        builder.row(InlineKeyboardButton(
            text=f"❌ {e['display_name']}",
            callback_data=f"fake_lb_del_{e['id']}"
        ))
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="admin_panel"))
    lines = [f"🏆 <b>FAKE LEADERBOARD</b>\n{SEP}"]
    for e in entries:
        lines.append(f"#{e['id']} {e['display_name']} — {e['total_wagered']:,.0f} T")
    try:
        await callback.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=builder.as_markup())
    except:
        await callback.message.answer("\n".join(lines), parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


class FakeLbFSM(StatesGroup):
    name = State()
    wager = State()


@dp.callback_query(F.data == "fake_lb_add")
async def cb_fake_lb_add(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Admin only!", show_alert=True); return
    await state.set_state(FakeLbFSM.name)
    try:
        await callback.message.edit_text("Send display name for fake entry:", reply_markup=back_kb("admin_fake_lb"))
    except:
        await callback.message.answer("Send display name:")
    await callback.answer()


@dp.message(FakeLbFSM.name)
async def msg_fake_lb_name(message: Message, state: FSMContext):
    await state.update_data(fake_name=message.text.strip())
    await state.set_state(FakeLbFSM.wager)
    await message.answer("Send wager amount (e.g. 500000):")


@dp.message(FakeLbFSM.wager)
async def msg_fake_lb_wager(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    try:
        wager = float(message.text.strip())
    except:
        await message.answer(error_text("Invalid amount"), parse_mode="HTML"); return
    await db.add_fake_leader(data["fake_name"], wager)
    await message.answer(success_text(f"✅ Added: {data['fake_name']} — {wager:,.0f} T"), parse_mode="HTML", reply_markup=back_kb("admin_fake_lb"))


@dp.callback_query(F.data.startswith("fake_lb_del_"))
async def cb_fake_lb_del(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Admin only!", show_alert=True); return
    fid = int(callback.data.split("_")[-1])
    await db.remove_fake_leader(fid)
    await callback.answer("✅ Removed!", show_alert=True)


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
        is_admin = message.from_user.id in ADMIN_IDS
        text = main_menu_text(user.get("username") or str(message.from_user.id), user["token_balance"])
        await message.answer(text, parse_mode="HTML", reply_markup=main_menu_kb(is_admin))
    else:
        await message.answer("Please use /start to register.")


# ─── STARTUP ──────────────────────────────────────────────────────────────────

async def main():
    await db.init()
    import aiosqlite
    async with aiosqlite.connect(db.db_path) as _db:
        await _db.execute("DELETE FROM balance_locks")
        await _db.commit()
    logger.info("🎰 Casino Bot (Token System) started!")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
