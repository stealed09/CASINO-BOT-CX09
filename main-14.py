import asyncio
import random
import string
import os
from aiohttp import web
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
    withdraw_method_kb, oxapay_currency_kb, support_reply_kb,
    vip_menu_kb, rakeback_kb, missions_kb, lootbox_kb,
    crash_autocashout_kb, pvp_menu_kb, pvp_join_kb,
    rain_catch_kb, provably_fair_kb, admin_new_features_kb,
)
from vip import get_vip_level, get_next_vip_level, vip_profile_text, vip_levels_info_text
from rakeback import (
    calculate_daily_rakeback, calculate_weekly_rakeback,
    can_claim_daily, can_claim_weekly, record_claim, rakeback_menu_text
)
from missions import MISSIONS, missions_text, claimable_missions
from lootbox import open_case, cases_menu_text, case_open_text, get_case, CASES
from games.crash import run_crash_game, cashout_crash, active_crash_games, generate_crash_point
from games.slots import spin_reels, get_multiplier, slot_result_text, slots_help_text
from games.pvp import (
    create_duel, join_duel, resolve_duel, duel_result_text,
    duel_waiting_text, get_open_duels, cancel_duel, auto_expire_duel, active_duels
)
from rain import create_rain, join_rain, finish_rain, rain_announce_text, rain_result_text, get_active_rain
from provably_fair import (
    get_or_create_seed_pair, increment_nonce, rotate_server_seed,
    set_client_seed, hash_server_seed, provably_fair_info_text
)
from activity_feed import add_real_event, feed_text
from ui.messages import (
    main_menu_text, wallet_text, referral_text, bonus_text,
    game_result_text, history_text, error_text, success_text,
    leaderboard_text, SEP
)
from games.dice import play_dice, play_dice_easy, play_dice_crazy, resolve_dice_crazy, _crazy_pending
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
    cmd_regencode,
    show_admin_stats, show_admin_settings, show_crypto_manager,
    show_admin_wager, show_wager_by_period, show_user_full_detail,
    show_user_lookup_prompt,
    cmd_add_balance, cmd_remove_balance, cmd_set_balance,
    cmd_broadcast, cmd_tip, cmd_gencode
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ─── FSM ──────────────────────────────────────────────────────────────────────

class GameBetFSM(StatesGroup):
    waiting_bet = State()

class GenCodeFSM(StatesGroup):
    waiting_amount = State()


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

class CrashFSM(StatesGroup):
    waiting_bet = State()
    waiting_autocashout = State()

class SlotsFSM(StatesGroup):
    waiting_bet = State()

class PvpFSM(StatesGroup):
    waiting_bet = State()

class RainFSM(StatesGroup):
    waiting_amount = State()
    waiting_winners = State()

class PfFSM(StatesGroup):
    waiting_seed = State()


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
    "aset_lb_min_wager":        ("leaderboard_min_wager", "Enter minimum wager to show real users on leaderboard (e.g. 1000):\nReal users below this won't appear. Fake entries always show."),
    "aset_user_tip_toggle":     ("user_tip_enabled", "Send <b>1</b> to enable or <b>0</b> to disable user-to-user tips:"),
    "aset_user_tip_min":        ("user_tip_min", "Enter minimum tip amount in Tokens (e.g. 10):"),
    "aset_user_tip_max":        ("user_tip_max", "Enter maximum tip amount in Tokens (e.g. 10000, or 0 for no limit):"),
    "aset_rain_group_id":       ("rain_group_id", "Enter the Group Chat ID where rain announcements will be sent (e.g. -1001234567890):"),
    "aset_crash_min_bet":       ("crash_min_bet", "Enter minimum Crash bet in Tokens (e.g. 10):"),
    "aset_crash_max_bet":       ("crash_max_bet", "Enter maximum Crash bet in Tokens (e.g. 10000):"),
    "aset_slots_min_bet":       ("slots_min_bet", "Enter minimum Slots bet in Tokens (e.g. 10):"),
    "aset_slots_max_bet":       ("slots_max_bet", "Enter maximum Slots bet in Tokens (e.g. 5000):"),
    "aset_pvp_house_fee":       ("pvp_house_fee", "Enter PVP house fee % (e.g. 5):"),
    "aset_rakeback_weekly_pct": ("rakeback_weekly_pct", "Enter weekly rakeback % (e.g. 1):"),
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
        base = round(wager * pct / 100, 4)
    else:
        key = "weekly_bonus_tokens" if bonus_type == "weekly" else "monthly_bonus_tokens"
        base = float(await db.get_setting(key) or "0")
    # Apply VIP bonus multiplier
    vip_enabled = await db.get_setting("vip_enabled")
    if vip_enabled == "1" and bonus_type == "weekly":
        from vip import get_vip_level
        vip = get_vip_level(user.get("total_wagered", 0))
        base = round(base * vip.get("weekly_bonus_multiplier", 1.0), 4)
    return base


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
    ref_pct = float(await db.get_setting("referral_percent") or "1")
    async with __import__("aiosqlite").connect(db.db_path) as _db:
        async with _db.execute("SELECT COUNT(*) FROM users WHERE referral_id=?", (callback.from_user.id,)) as cur:
            row = await cur.fetchone()
            ref_count = row[0] if row else 0
    try:
        await callback.message.edit_text(
            referral_text(user, ref_count, me.username, ref_pct),
            parse_mode="HTML", reply_markup=back_kb()
        )
    except:
        await callback.message.answer(referral_text(user, ref_count, me.username, ref_pct), parse_mode="HTML")
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
    wager_pct_w = await db.get_setting("bonus_wager_percent_weekly") or "1"
    wager_pct_m = await db.get_setting("bonus_wager_percent_monthly") or "2"
    can_w = await can_claim_bonus(user, "weekly")
    can_m = await can_claim_bonus(user, "monthly")
    try:
        await callback.message.edit_text(
            bonus_text(user, weekly, monthly, mode, tag, wager_pct_w, wager_pct_m),
            parse_mode="HTML", reply_markup=bonus_claim_kb(can_w, can_m)
        )
    except:
        await callback.message.answer(bonus_text(user, weekly, monthly, mode, tag, wager_pct_w, wager_pct_m), parse_mode="HTML", reply_markup=bonus_claim_kb(can_w, can_m))
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
    wager_pct_w = await db.get_setting("bonus_wager_percent_weekly") or "1"
    wager_pct_m = await db.get_setting("bonus_wager_percent_monthly") or "2"
    can_w = await can_claim_bonus(user, "weekly")
    can_m = await can_claim_bonus(user, "monthly")
    try:
        await callback.message.edit_text(bonus_text(user, weekly, monthly, mode, tag, wager_pct_w, wager_pct_m), parse_mode="HTML", reply_markup=bonus_claim_kb(can_w, can_m))
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
    min_wager = float(await db.get_setting("leaderboard_min_wager") or "0")
    text = leaderboard_text(entries, "lifetime", fake, min_wager)
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
    min_wager = float(await db.get_setting("leaderboard_min_wager") or "0")
    text = leaderboard_text(entries, period, fake, min_wager)
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


@dp.callback_query(F.data == "withdraw_crypto_select")
async def cb_withdraw_crypto_select(callback: CallbackQuery, state: FSMContext):
    """User types currency themselves — no menu."""
    user = await db.get_user(callback.from_user.id)
    wd_tax = await db.get_effective_withdraw_tax(callback.from_user.id)
    min_wd = await db.get_setting("min_withdrawal_tokens") or "100"
    await state.set_state(WithdrawFSM.crypto_symbol)
    try:
        await callback.message.edit_text(
            f"₿ <b>CRYPTO WITHDRAWAL</b>\n{SEP}\n"
            f"🪙 Balance: <b>{user['token_balance']:,.4f} Tokens</b>\n"
            f"📉 Minimum: <b>{min_wd} Tokens</b>\n"
            f"🧾 Tax: <b>{wd_tax}%</b>\n\n"
            f"Enter your <b>crypto currency</b>:\n"
            f"Example: <code>USDT</code>, <code>BTC</code>, <code>ETH</code>, <code>LTC</code>",
            parse_mode="HTML", reply_markup=back_kb("wallet_withdraw")
        )
    except:
        await callback.message.answer("Enter crypto currency (e.g. USDT, BTC):")
    await callback.answer()


@dp.message(WithdrawFSM.crypto_symbol)
async def msg_withdraw_crypto_symbol(message: Message, state: FSMContext):
    symbol = message.text.strip().upper()
    if not symbol or len(symbol) > 10:
        await message.answer(error_text("Enter valid currency e.g. <code>USDT</code>"), parse_mode="HTML"); return
    user = await db.get_user(message.from_user.id)
    wd_tax = await db.get_effective_withdraw_tax(message.from_user.id)
    min_wd = await db.get_setting("min_withdrawal_tokens") or "100"
    await state.update_data(crypto_symbol=symbol)
    await state.set_state(WithdrawFSM.crypto_token_amount)
    await message.answer(
        f"₿ <b>{symbol} WITHDRAWAL</b>\n{SEP}\n"
        f"🪙 Balance: <b>{user['token_balance']:,.4f} Tokens</b>\n"
        f"📉 Minimum: <b>{min_wd} Tokens</b>\n"
        f"🧾 Tax: <b>{wd_tax}%</b>\n\n"
        f"Enter <b>token amount</b> to withdraw:",
        parse_mode="HTML", reply_markup=back_kb("wallet_withdraw")
    )


@dp.message(WithdrawFSM.crypto_token_amount)
async def msg_withdraw_crypto_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(",", ""))
        if amount <= 0: raise ValueError
    except:
        await message.answer(error_text("Enter valid amount"), parse_mode="HTML"); return
    await state.update_data(crypto_wd_amount=amount)
    await state.set_state(WithdrawFSM.crypto_address)
    data = await state.get_data()
    symbol = data.get("crypto_symbol", "")
    await message.answer(
        f"📬 Enter your <b>{symbol}</b> wallet address\n"
        f"<i>(also mention your network e.g. TRC20, ERC20)</i>:",
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

    # Each game function self-manages: locks balance, plays, unlocks, updates balance
    try:
        await play_fn(message, bot, amount)
        await pay_referral_bonus(user_id, amount)
    except Exception as e:
        logger.error(f"Game error [{game_name}] user={user_id}: {e}")
        await message.answer(error_text("Game error. Please try again."), parse_mode="HTML")


@dp.message(Command("dice", "d"))
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


@dp.message(Command("darts", "dt"))
async def cmd_darts(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: <code>/darts amount</code>", parse_mode="HTML"); return
    try:
        amount = float(parts[1])
    except:
        await message.answer(error_text("Invalid amount"), parse_mode="HTML"); return
    await _play_game(message, amount, play_darts, "Darts")


@dp.message(Command("limbo", "lb"))
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
    await check_and_process_bonus_eligibility(
        callback.from_user.id, callback.from_user.first_name or "",
        callback.from_user.last_name or "", callback.from_user.username or ""
    )
    try:
        await play_coinflip(callback, bot, amount, choice)
        await pay_referral_bonus(callback.from_user.id, amount)
    except Exception as e:
        logger.error(f"CoinFlip error: {e}")
    await callback.answer()


GAME_META = {
    "dice":     ("🎲", "DICE",       "dice"),
    "bask":     ("🏀", "BASKETBALL", "bask"),
    "ball":     ("⚽", "SOCCER",     "ball"),
    "bowl":     ("🎳", "BOWLING",    "bowl"),
    "darts":    ("🎯", "DARTS",      "darts"),
    "limbo":    ("🚀", "LIMBO",      "limbo"),
    "coinflip": ("🪙", "COIN FLIP",  "cf"),
}


@dp.callback_query(F.data == "game_crash")
async def cb_crash_menu(callback: CallbackQuery, state: FSMContext):
    enabled = await db.get_setting("crash_enabled")
    if enabled != "1":
        await callback.answer("Crash is currently disabled.", show_alert=True); return
    min_bet = await db.get_setting("crash_min_bet") or "10"
    max_bet = await db.get_setting("crash_max_bet") or "10000"
    await state.set_state(CrashFSM.waiting_bet)
    text = (
        f"🚀 <b>CRASH GAME</b>\n{SEP}\n"
        f"💵 Min bet: <b>{min_bet}</b> | Max: <b>{max_bet}</b> Tokens\n\n"
        f"Multiplier rises from 1.00x — cashout before CRASH!\n"
        f"Send your bet amount:"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_kb("menu_games"))
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=back_kb("menu_games"))
    await callback.answer()


@dp.message(CrashFSM.waiting_bet)
async def crash_bet_input(message: Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        bet = float(message.text.strip().replace(",", ""))
        if bet <= 0: raise ValueError
    except:
        await message.reply(error_text("❌ Invalid amount. Send a number."), parse_mode="HTML")
        return
    min_bet = float(await db.get_setting("crash_min_bet") or "10")
    max_bet = float(await db.get_setting("crash_max_bet") or "10000")
    if bet < min_bet:
        await message.reply(error_text(f"❌ Min bet is {min_bet:,.0f} Tokens."), parse_mode="HTML"); return
    if bet > max_bet:
        await message.reply(error_text(f"❌ Max bet is {max_bet:,.0f} Tokens."), parse_mode="HTML"); return
    user = await db.get_user(user_id)
    if not user or user["token_balance"] < bet:
        await message.reply(error_text(f"❌ Insufficient balance! You have {user['token_balance']:,.4f} Tokens."), parse_mode="HTML")
        return
    await state.update_data(bet=bet)
    await state.set_state(CrashFSM.waiting_autocashout)
    await message.reply(
        f"🚀 Bet: <b>{bet:,.4f} Tokens</b>\n\nSet auto cashout multiplier:",
        parse_mode="HTML", reply_markup=crash_autocashout_kb()
    )


@dp.callback_query(F.data.startswith("crash_auto_"))
async def cb_crash_start(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    bet = data.get("bet")
    if not bet:
        await callback.answer("Session expired. Try again.", show_alert=True)
        await state.clear(); return
    auto_mult = float(callback.data.replace("crash_auto_", ""))
    auto_cashout = auto_mult if auto_mult > 0 else None
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    if not user or user["token_balance"] < bet:
        await callback.answer("Insufficient balance.", show_alert=True)
        await state.clear(); return
    # Deduct bet
    await db.update_token_balance(user_id, -bet)
    await db.update_wagered(user_id, bet)
    await db.update_mission_progress(user_id, wager=bet, games_played=1, crash_plays=1)
    # Generate crash point
    ss, cs, nonce = await get_or_create_seed_pair(user_id, db.db_path)
    crash_point = generate_crash_point(ss, cs, nonce)
    await increment_nonce(user_id, db.db_path)
    game_tax = float(await db.get_setting("game_tax_percent") or "5")
    # Send initial message
    from games.crash import crash_message
    msg = await callback.message.answer(
        crash_message(bet, 1.00, auto_cashout, server_seed_hash=hash_server_seed(ss)),
        parse_mode="HTML"
    )
    await state.clear()
    # Run crash loop
    asyncio.create_task(run_crash_game(
        bot, user_id, msg.chat.id, msg.message_id,
        bet, auto_cashout, crash_point, hash_server_seed(ss), db, game_tax
    ))
    await callback.answer()


@dp.callback_query(F.data == "crash_cashout")
async def cb_crash_cashout(callback: CallbackQuery):
    mult = await cashout_crash(callback.from_user.id)
    if mult:
        await callback.answer(f"💸 Cashed out at {mult:.2f}x!", show_alert=False)
    else:
        await callback.answer("No active crash game or already resolved.", show_alert=True)


@dp.message(Command("cashout"))
async def cmd_cashout(message: Message):
    mult = await cashout_crash(message.from_user.id)
    if mult:
        await message.reply(f"💸 Cashing out at <b>{mult:.2f}x</b>!", parse_mode="HTML")
    else:
        await message.reply(error_text("❌ No active crash game."), parse_mode="HTML")


# ═══════════════════════════════════════════════════════════════════════════════
# ─── SLOTS ────────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════


@dp.callback_query(F.data == "game_slots")
async def cb_slots_menu(callback: CallbackQuery, state: FSMContext):
    enabled = await db.get_setting("slots_enabled")
    if enabled != "1":
        await callback.answer("Slots are currently disabled.", show_alert=True); return
    min_bet = await db.get_setting("slots_min_bet") or "10"
    max_bet = await db.get_setting("slots_max_bet") or "5000"
    await state.set_state(SlotsFSM.waiting_bet)
    text = (
        f"🎰 <b>SLOT MACHINE</b>\n{SEP}\n"
        f"💵 Min: <b>{min_bet}</b> | Max: <b>{max_bet}</b> Tokens\n\n"
        f"Send your bet amount:"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_kb("menu_games"))
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=back_kb("menu_games"))
    await callback.answer()


@dp.message(SlotsFSM.waiting_bet)
async def slots_bet_input(message: Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        bet = float(message.text.strip().replace(",", ""))
        if bet <= 0: raise ValueError
    except:
        await message.reply(error_text("❌ Invalid amount."), parse_mode="HTML")
        return
    min_bet = float(await db.get_setting("slots_min_bet") or "10")
    max_bet = float(await db.get_setting("slots_max_bet") or "5000")
    if bet < min_bet:
        await message.reply(error_text(f"❌ Min bet is {min_bet:,.0f} Tokens."), parse_mode="HTML"); return
    if bet > max_bet:
        await message.reply(error_text(f"❌ Max bet is {max_bet:,.0f} Tokens."), parse_mode="HTML"); return
    user = await db.get_user(user_id)
    if not user or user["token_balance"] < bet:
        await message.reply(error_text(f"❌ Insufficient balance! You have {user['token_balance']:,.4f} Tokens."), parse_mode="HTML")
        return
    await db.update_token_balance(user_id, -bet)
    await db.update_wagered(user_id, bet)
    await db.update_mission_progress(user_id, wager=bet, games_played=1)
    reels = spin_reels()
    game_tax = float(await db.get_setting("game_tax_percent") or "5")
    multiplier, label = get_multiplier(reels)
    text, net = slot_result_text(reels, bet, multiplier, label, game_tax)
    if net > 0:
        await db.update_token_balance(user_id, net)
        await db.add_transaction(user_id, "slots_win", net, "completed", "TOKEN")
        add_real_event(message.from_user.first_name or str(user_id), "Slots", net)
    else:
        await db.add_transaction(user_id, "slots_loss", bet, "completed", "TOKEN")
    await state.clear()
    await message.reply(text, parse_mode="HTML", reply_markup=back_to_main_kb())


@dp.message(Command("slots"))
async def cmd_slots(message: Message, state: FSMContext):
    enabled = await db.get_setting("slots_enabled")
    if enabled != "1":
        await message.reply(error_text("❌ Slots are currently disabled."), parse_mode="HTML"); return
    await state.set_state(SlotsFSM.waiting_bet)
    await message.reply(
        f"🎰 <b>SLOT MACHINE</b>\n{SEP}\nSend your bet amount:",
        parse_mode="HTML", reply_markup=back_kb("menu_games")
    )



@dp.callback_query(F.data.startswith("game_"))
async def cb_game(callback: CallbackQuery, state: FSMContext):
    cmd = callback.data[5:]
    # These have their own dedicated handlers — skip here
    if cmd in ("crash", "slots"):
        return
    meta = GAME_META.get(cmd)
    if not meta:
        await callback.answer("Unknown game", show_alert=True); return
    emoji, name, short = meta
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Use /start first!", show_alert=True); return
    if user.get("is_banned"):
        await callback.answer("Account banned!", show_alert=True); return
    await state.update_data(game_key=cmd)
    await state.set_state(GameBetFSM.waiting_bet)
    try:
        await callback.message.edit_text(
            f"{emoji} <b>{name}</b>\n{SEP}\n"
            f"🪙 Your Balance: <b>{user['token_balance']:,.4f} Tokens</b>\n\n"
            f"Enter your <b>bet amount</b>:\nExample: <code>100</code>",
            parse_mode="HTML", reply_markup=back_kb("menu_games")
        )
    except:
        await callback.message.answer(
            f"{emoji} <b>{name}</b>\n{SEP}\nEnter bet amount:",
            parse_mode="HTML", reply_markup=back_kb("menu_games")
        )
    await callback.answer()


@dp.message(GameBetFSM.waiting_bet)
async def msg_game_bet(message: Message, state: FSMContext):
    data = await state.get_data()
    game_key = data.get("game_key", "")
    try:
        amount = float(message.text.strip().replace(",", ""))
        if amount <= 0: raise ValueError
    except:
        await message.answer(error_text("Enter valid bet amount (e.g. 100)"), parse_mode="HTML"); return
    await state.clear()
    user = await db.get_user(message.from_user.id)
    if not user or user["token_balance"] < amount:
        await message.answer(error_text("Insufficient Tokens."), parse_mode="HTML"); return
    if await db.is_balance_locked(message.from_user.id):
        await message.answer(error_text("Game already in progress!"), parse_mode="HTML"); return
    await check_and_process_bonus_eligibility(
        message.from_user.id, message.from_user.first_name or "",
        message.from_user.last_name or "", message.from_user.username or ""
    )
    game_fns = {
        "dice":     play_dice,
        "bask":     play_basketball,
        "ball":     play_soccer,
        "bowl":     play_bowling,
        "darts":    play_darts,
        "limbo":    play_limbo,
    }
    if game_key == "coinflip":
        await prompt_coinflip(message, amount)
        return
    fn = game_fns.get(game_key)
    if not fn:
        await message.answer(error_text("Unknown game."), parse_mode="HTML"); return
    await _play_game(message, amount, fn, game_key.upper())


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
            f"💡 <b>TIP USER</b>\n{SEP}\n"
            f"Send: <code>/tip @username 500</code>\n"
            f"or: <code>/tip user_id 500</code>\n\n"
            f"Tokens will be credited instantly.",
            parse_mode="HTML", reply_markup=back_kb("admin_panel")
        )
    except: pass
    await callback.answer()


@dp.callback_query(F.data == "admin_regen_code")
async def cb_admin_regen_code(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS and not await db.is_sub_admin(callback.from_user.id):
        await callback.answer("Admin only!", show_alert=True); return
    codes = await db.get_all_redeem_codes()
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    # Show ALL codes (used + unused) so admin can regen any
    for c in (codes or [])[:10]:
        status = "✅" if c.get("used_by") else "🟢"
        builder.row(InlineKeyboardButton(
            text=f"♻️ {c['code']} ({c['token_amount']:,.0f}T) {status}",
            callback_data=f"regen_code_{c['code']}"
        ))
    builder.row(InlineKeyboardButton(text="➕ Generate New Code", callback_data="admin_gen_code_btn"))
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="admin_redeems"))
    try:
        await callback.message.edit_text(
            f"♻️ <b>REDEEM CODE MANAGER</b>\n{SEP}\n"
            f"Select a code to regenerate it,\nor generate a brand new one:",
            parse_mode="HTML", reply_markup=builder.as_markup()
        )
    except:
        await callback.message.answer("Select code:", reply_markup=builder.as_markup())
    await callback.answer()



@dp.callback_query(F.data == "admin_gen_code_btn")
async def cb_admin_gen_code_btn(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS and not await db.is_sub_admin(callback.from_user.id):
        await callback.answer("Admin only!", show_alert=True); return
    await state.set_state(GenCodeFSM.waiting_amount)
    try:
        await callback.message.edit_text(
            f"➕ <b>GENERATE NEW CODE</b>\n{SEP}\n"
            f"Enter token amount:\nExample: <code>5000</code>",
            parse_mode="HTML", reply_markup=back_kb("admin_regen_code")
        )
    except:
        await callback.message.answer("Enter token amount:")
    await callback.answer()


@dp.message(GenCodeFSM.waiting_amount)
async def msg_gen_code_amount(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS and not await db.is_sub_admin(message.from_user.id):
        return
    try:
        amount = float(message.text.strip().replace(",", ""))
        if amount <= 0: raise ValueError
    except:
        await message.answer(error_text("Enter valid amount e.g. <code>5000</code>"), parse_mode="HTML"); return
    await state.clear()
    import random, string
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    ok = await db.create_redeem_code(code, amount, message.from_user.id)
    if ok:
        await message.answer(
            success_text(f"✅ New Code Generated!\n🎟️ Code: <code>{code}</code>\n🪙 Tokens: <b>{amount:,.0f}</b>"),
            parse_mode="HTML", reply_markup=back_kb("admin_redeems")
        )
    else:
        await message.answer(error_text("Error generating code. Try again."), parse_mode="HTML")


@dp.callback_query(F.data.startswith("regen_code_"))
async def cb_regen_specific_code(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS and not await db.is_sub_admin(callback.from_user.id):
        await callback.answer("Admin only!", show_alert=True); return
    code = callback.data.replace("regen_code_", "")
    await cmd_regencode(callback, bot, code)
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
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()

    if not codes:
        text = f"🎟️ <b>REDEEM CODES</b>\n{SEP}\nNo codes yet.\nCreate: <code>/gencode amount [name]</code>"
    else:
        lines = [f"🎟️ <b>REDEEM CODES</b>\n{SEP}"]
        for c in codes:
            status = f"✅ Used by <code>{c['used_by']}</code>" if c["used_by"] else "🟢 Available"
            lines.append(f"<code>{c['code']}</code> — {c['token_amount']:,.0f} T — {status}")
        text = "\n".join(lines)
        if len(text) > 4000: text = text[:4000] + "\n..."

    # Always show Regenerate button below
    builder.row(InlineKeyboardButton(text="♻️ Regenerate a Code", callback_data="admin_regen_code"))
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="admin_panel"))

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@dp.callback_query(F.data.startswith("aset_"))
async def cb_admin_set(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS and not await db.is_sub_admin(callback.from_user.id):
        await callback.answer("Admin only!", show_alert=True); return

    # Direct toggle keys — flip ON/OFF immediately, no text input needed
    DIRECT_TOGGLES = {
        "aset_vip_enabled":         "vip_enabled",
        "aset_rakeback_enabled":    "rakeback_enabled",
        "aset_missions_enabled":    "missions_enabled",
        "aset_lootbox_enabled":     "lootbox_enabled",
        "aset_crash_enabled":       "crash_enabled",
        "aset_slots_enabled":       "slots_enabled",
        "aset_live_feed_enabled":   "live_feed_enabled",
        "aset_rain_enabled":        "rain_enabled",
    }
    if callback.data in DIRECT_TOGGLES:
        db_key = DIRECT_TOGGLES[callback.data]
        current = await db.get_setting(db_key)
        new_val = "0" if current == "1" else "1"
        await db.set_setting(db_key, new_val)
        status = "🟢 ON" if new_val == "1" else "🔴 OFF"
        await callback.answer(f"{db_key}: {status}", show_alert=True)
        await cb_admin_new_features(callback)
        return

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
    """
    ADMIN:  /tip @username 500  OR  /tip user_id 500  (no balance check, free tip)
    USER:   /tip @username 500  OR  reply to message + /tip 500  (balance deducted)
    """
    sender_id = message.from_user.id
    is_admin = sender_id in ADMIN_IDS or await db.is_sub_admin(sender_id)

    parts = message.text.split()

    # ── Parse amount ─────────────────────────────────────────────────
    # Admin:  /tip @user 500  → amount is parts[2]
    # User:   /tip @user 500  → amount is parts[2]
    #         /tip 500        → amount is parts[1]  (reply mode)
    amount = None
    for p in parts[1:]:
        try:
            v = float(p)
            if v > 0:
                amount = v
                break
        except:
            continue

    if not amount:
        await message.reply(
            "ℹ️ <b>Tip Usage:</b>\n"
            "• <code>/tip @username 500</code>\n"
            "• Reply to someone's message → <code>/tip 500</code>",
            parse_mode="HTML"
        )
        return

    # ── Find target ───────────────────────────────────────────────────
    target_id = None
    target_name = None

    # 1. @mention or text_mention in message entities
    if message.entities:
        for ent in message.entities:
            if ent.type == "text_mention" and ent.user:
                target_id = ent.user.id
                target_name = ent.user.first_name or str(ent.user.id)
                break
            if ent.type == "mention":
                username = message.text[ent.offset:ent.offset + ent.length].lstrip("@")
                u = await db.get_user_by_username(username)
                if u:
                    target_id = u["user_id"]
                    target_name = f"@{username}"
                else:
                    await message.reply(error_text(f"❌ @{username} not found in bot."), parse_mode="HTML")
                    return
                break

    # 2. Reply to a message — skip if replied message is from a bot,
    #    then also check if that bot message itself is quoting a real user
    if not target_id and message.reply_to_message:
        rep_msg = message.reply_to_message
        rep_user = rep_msg.from_user
        if rep_user and not rep_user.is_bot:
            target_id = rep_user.id
            target_name = rep_user.first_name or str(rep_user.id)
        elif rep_user and rep_user.is_bot:
            # Bot replied to a bot message — try to find the original user
            # from the quoted/forwarded sender inside the bot's message
            if rep_msg.reply_to_message and rep_msg.reply_to_message.from_user:
                orig = rep_msg.reply_to_message.from_user
                if not orig.is_bot:
                    target_id = orig.id
                    target_name = orig.first_name or str(orig.id)

    # 3. Admin fallback — /tip user_id 500
    if not target_id and is_admin:
        await cmd_tip(message, bot)
        return

    if not target_id:
        await message.reply(
            "ℹ️ <b>Tip Usage:</b>\n"
            "• <code>/tip @username 500</code>\n"
            "• Reply to someone's message → <code>/tip 500</code>",
            parse_mode="HTML"
        )
        return

    if target_id == sender_id:
        await message.reply(error_text("❌ You cannot tip yourself!"), parse_mode="HTML")
        return

    target_user = await db.get_user(target_id)
    if not target_user:
        await message.reply(error_text("❌ That user is not registered in the bot!"), parse_mode="HTML")
        return

    # ── Admin tip — free, no balance deduction ────────────────────────
    if is_admin:
        await db.update_token_balance(target_id, amount)
        await db.add_transaction(target_id, "tip_received", amount, "completed", currency="TOKEN")
        await message.reply(
            success_text(f"🎁 Tipped <b>{amount:,.4f}</b> Tokens to <b>{target_name}</b>!"),
            parse_mode="HTML"
        )
        try:
            await bot.send_message(target_id, success_text(f"🎁 Admin tipped you <b>{amount:,.4f}</b> Tokens!"), parse_mode="HTML")
        except:
            pass
        return

    # ── User tip — check feature enabled + balance ────────────────────
    tip_enabled = await db.get_setting("user_tip_enabled")
    if tip_enabled != "1":
        await message.reply(error_text("❌ User tips are currently disabled."), parse_mode="HTML")
        return

    tip_min = float(await db.get_setting("user_tip_min") or "1")
    tip_max = float(await db.get_setting("user_tip_max") or "0")

    if amount < tip_min:
        await message.reply(error_text(f"❌ Minimum tip is <b>{tip_min:,.0f}</b> Tokens."), parse_mode="HTML")
        return
    if tip_max > 0 and amount > tip_max:
        await message.reply(error_text(f"❌ Maximum tip is <b>{tip_max:,.0f}</b> Tokens."), parse_mode="HTML")
        return

    sender = await db.get_user(sender_id)
    if not sender:
        await message.reply(error_text("❌ Please start the bot first!"), parse_mode="HTML")
        return
    if sender["token_balance"] < amount:
        await message.reply(
            error_text(f"❌ Insufficient balance! You have <b>{sender['token_balance']:,.4f}</b> Tokens."),
            parse_mode="HTML"
        )
        return

    await db.update_token_balance(sender_id, -amount)
    await db.update_token_balance(target_id, amount)
    await db.add_transaction(sender_id, "tip_sent", amount, "completed", currency="TOKEN")
    await db.add_transaction(target_id, "tip_received", amount, "completed", currency="TOKEN")

    sender_name = message.from_user.first_name or str(sender_id)
    new_balance = sender["token_balance"] - amount

    await message.reply(
        f"🎁 <b>TIP SENT!</b>\n{SEP}\n"
        f"To: <b>{target_name}</b>\n"
        f"💰 Amount: <b>{amount:,.4f} Tokens</b>\n"
        f"🪙 Your Balance: <b>{new_balance:,.4f}</b>",
        parse_mode="HTML"
    )
    try:
        await bot.send_message(
            target_id,
            f"🎁 <b>YOU RECEIVED A TIP!</b>\n{SEP}\n"
            f"From: <b>{sender_name}</b>\n"
            f"💰 Amount: <b>+{amount:,.4f} Tokens</b>\n"
            f"🪙 Balance: <b>{target_user['token_balance'] + amount:,.4f}</b>",
            parse_mode="HTML"
        )
    except:
        pass


@dp.message(Command("send"))
async def cmd_user_tip(message: Message):
    """
    User-to-user tip in group by replying to a message.
    Usage: reply to a user's message and send /send <amount>
    """
    # Check feature enabled
    tip_enabled = await db.get_setting("user_tip_enabled")
    if tip_enabled != "1":
        await message.reply(error_text("❌ User tips are currently disabled."), parse_mode="HTML")
        return

    # Must be a reply
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply(
            "ℹ️ <b>How to tip:</b>\nReply to someone's message and send:\n<code>/send 100</code>",
            parse_mode="HTML"
        )
        return

    target = message.reply_to_message.from_user
    sender_id = message.from_user.id
    target_id = target.id

    if target_id == sender_id:
        await message.reply(error_text("❌ You can't tip yourself!"), parse_mode="HTML")
        return

    if target.is_bot:
        await message.reply(error_text("❌ You can't tip a bot!"), parse_mode="HTML")
        return

    # Parse amount
    parts = message.text.split()
    try:
        amount = float(parts[1])
        if amount <= 0:
            raise ValueError
    except:
        await message.reply("Usage: <code>/send &lt;amount&gt;</code> (reply to user's message)", parse_mode="HTML")
        return

    # Check min/max
    tip_min = float(await db.get_setting("user_tip_min") or "1")
    tip_max = float(await db.get_setting("user_tip_max") or "0")
    if amount < tip_min:
        await message.reply(error_text(f"❌ Minimum tip is <b>{tip_min:,.0f}</b> Tokens."), parse_mode="HTML")
        return
    if tip_max > 0 and amount > tip_max:
        await message.reply(error_text(f"❌ Maximum tip is <b>{tip_max:,.0f}</b> Tokens."), parse_mode="HTML")
        return

    # Check sender balance
    sender = await db.get_user(sender_id)
    if not sender:
        await message.reply(error_text("❌ You are not registered. Start the bot first!"), parse_mode="HTML")
        return
    if sender["token_balance"] < amount:
        await message.reply(error_text(f"❌ Insufficient balance! You have <b>{sender['token_balance']:,.4f}</b> Tokens."), parse_mode="HTML")
        return

    # Check target registered
    target_user = await db.get_user(target_id)
    if not target_user:
        await message.reply(error_text("❌ That user is not registered in the bot!"), parse_mode="HTML")
        return

    # Transfer
    await db.update_token_balance(sender_id, -amount)
    await db.update_token_balance(target_id, amount)
    await db.add_transaction(sender_id, "tip_sent", amount, "completed", currency="TOKEN")
    await db.add_transaction(target_id, "tip_received", amount, "completed", currency="TOKEN")

    sender_name = message.from_user.first_name or str(sender_id)
    target_name = target.first_name or str(target_id)
    new_balance = sender["token_balance"] - amount

    await message.reply(
        f"🎁 <b>TIP SENT!</b>\n{SEP}\n"
        f"From: <b>{sender_name}</b>\n"
        f"To: <b>{target_name}</b>\n"
        f"💰 Amount: <b>{amount:,.4f} Tokens</b>\n"
        f"🪙 Your Balance: <b>{new_balance:,.4f}</b>",
        parse_mode="HTML"
    )
    try:
        await bot.send_message(
            target_id,
            f"🎁 <b>YOU RECEIVED A TIP!</b>\n{SEP}\n"
            f"From: <b>{sender_name}</b>\n"
            f"💰 Amount: <b>+{amount:,.4f} Tokens</b>\n"
            f"🪙 Balance: <b>{target_user['token_balance'] + amount:,.4f}</b>",
            parse_mode="HTML"
        )
    except:
        pass


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
    await callback.answer()


# ─── DICE CRAZY — USER SENDS DICE ─────────────────────────────────────────────

@dp.message(F.dice)
async def on_dice_message(message: Message):
    """Handle physical dice sent by user — resolves crazy mode session."""
    user_id = message.from_user.id
    if user_id not in _crazy_pending:
        return  # Not in crazy mode, ignore
    emoji = message.dice.emoji
    if emoji != "🎲":
        return  # Only handle dice, not other emojis
    pending_bet = _crazy_pending.get(user_id, {}).get("bet", 0)
    await asyncio.sleep(4)  # Wait for animation
    val = message.dice.value
    await resolve_dice_crazy(user_id, val, bot)
    if pending_bet > 0:
        await pay_referral_bonus(user_id, pending_bet)




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
    await _send_help(message)


# ─── SLASH COMMAND ALIASES (work in groups + private) ─────────────────────────

@dp.message(Command("refer", "referral"))
async def cmd_refer_alias(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.reply("Please start the bot first: /start"); return
    me = await bot.get_me()
    ref_pct = float(await db.get_setting("referral_percent") or "1")
    async with __import__("aiosqlite").connect(db.db_path) as _db:
        async with _db.execute("SELECT COUNT(*) FROM users WHERE referral_id=?", (message.from_user.id,)) as cur:
            row = await cur.fetchone()
            ref_count = row[0] if row else 0
    await message.reply(referral_text(user, ref_count, me.username, ref_pct), parse_mode="HTML")


@dp.message(Command("leaderboard", "lb"))
async def cmd_leaderboard_alias(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.reply("Please start the bot first: /start"); return
    entries = await db.get_top_wagers("lifetime", 10)
    fake = await db.get_fake_leaderboard()
    min_wager = float(await db.get_setting("leaderboard_min_wager") or "0")
    text = leaderboard_text(entries, "lifetime", fake, min_wager)
    await message.reply(text, parse_mode="HTML", reply_markup=leaderboard_kb())


@dp.message(Command("balance", "bal"))
async def cmd_balance_alias(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.reply("Please start the bot first: /start"); return
    await message.reply(wallet_text(user), parse_mode="HTML", reply_markup=wallet_kb())


@dp.message(Command("deposit", "dep"))
async def cmd_deposit_alias(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.reply("Please start the bot first: /start"); return
    dep_tax = await db.get_effective_deposit_tax(message.from_user.id)
    inr_rate = await db.get_setting("inr_to_token_rate") or "1"
    stars_rate = await db.get_setting("stars_to_token_rate") or "1"
    await message.reply(
        f"💳 <b>DEPOSIT</b>\n{SEP}\n"
        f"🪙 Token Rates:\n"
        f"  🏦 INR: ₹1 = <b>{inr_rate} Token(s)</b>\n"
        f"  ⭐ Stars: 1★ = <b>{stars_rate} Token(s)</b>\n"
        f"  ₿ Crypto: varies by coin\n"
        f"🧾 Your Deposit Tax: <b>{dep_tax}%</b>\n"
        f"{SEP}\nChoose deposit method:",
        parse_mode="HTML", reply_markup=deposit_method_kb()
    )


@dp.message(Command("withdrawal", "withdraw", "wd"))
async def cmd_withdraw_alias(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.reply("Please start the bot first: /start"); return
    wd_tax = await db.get_effective_withdraw_tax(message.from_user.id)
    min_wd = await db.get_setting("min_withdrawal_tokens") or "100"
    cryptos = await db.get_all_cryptos()
    await message.reply(
        f"💸 <b>WITHDRAW</b>\n{SEP}\n"
        f"🪙 Balance: <b>{user['token_balance']:,.4f} Tokens</b>\n"
        f"📉 Minimum: <b>{min_wd} Tokens</b>\n"
        f"🧾 Your Tax: <b>{wd_tax}%</b>\n"
        f"{SEP}\nChoose withdrawal method:",
        parse_mode="HTML", reply_markup=withdraw_method_kb(cryptos)
    )


@dp.callback_query(F.data == "menu_help")
async def cb_help(callback: CallbackQuery):
    help_text = _build_help_text()
    try:
        await callback.message.edit_text(help_text, parse_mode="HTML", reply_markup=back_kb("menu_main"))
    except:
        await callback.message.answer(help_text, parse_mode="HTML", reply_markup=back_kb("menu_main"))
    await callback.answer()


def _build_help_text() -> str:
    return (
        f"❓ <b>HELP & GAME RULES</b>\n{SEP}\n"
        f"<b>🎲 Dice</b>\n"
        f"  😊 Easy — Roll ≥4 = WIN (1.9x)\n"
        f"  🔥 Crazy — Bot rolls, then YOU physically send a 🎲 — beat bot = WIN (2x)\n\n"
        f"<b>🚀 Limbo</b>\n"
        f"  Pick a multiplier (2x–100x)\n"
        f"  Rocket must reach your target to win!\n"
        f"  Higher multiplier = bigger win, lower chance\n\n"
        f"<b>🪙 Coin Flip</b>\n"
        f"  Pick 👑 Heads or 🦅 Tails — 50/50 (1.9x)\n\n"
        f"<b>🏀 Basketball</b> | <b>⚽ Soccer</b> | <b>🎳 Bowling</b> | <b>🎯 Darts</b>\n"
        f"  All use Telegram's built-in dice emojis — pure luck!\n\n"
        f"{SEP}\n"
        f"<b>💸 Withdrawals</b>\n"
        f"  Wallet → Withdraw → UPI or Crypto\n"
        f"  Confirm address/ID twice → Admin approves\n\n"
        f"<b>🎁 Bonus</b>\n"
        f"  Add the bot tag to first name, last name, or username\n"
        f"  Removing it gives 1 hour grace, then Day 1 reset!\n\n"
        f"<b>🎟️ Redeem Code</b>\n"
        f"  Main Menu → Redeem → Enter your code\n\n"
        f"{SEP}\n"
        f"⚠️ All wins have a small tax deducted (set by admin)\n"
        f"🆘 Issues? Use Support in main menu"
    )


async def _send_help(message: Message):
    await message.answer(_build_help_text(), parse_mode="HTML", reply_markup=back_kb("menu_main"))


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


# ─── STARTUP ──────────────────────────────────────────────────────────────────

async def main():
    await db.init()
    import aiosqlite
    async with aiosqlite.connect(db.db_path) as _db:
        await _db.execute("DELETE FROM balance_locks")
        await _db.commit()

    # ── Register slash commands ────────────────────────────────────────
    from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats
    private_commands = [
        BotCommand(command="start",       description="Start the bot ✨"),
        BotCommand(command="balance",     description="Check your balance 💰"),
        BotCommand(command="deposit",     description="Deposit tokens 💳"),
        BotCommand(command="withdrawal",  description="Withdraw tokens 💸"),
        BotCommand(command="refer",       description="Referral program 🤝"),
        BotCommand(command="leaderboard", description="Top players 🏆"),
        BotCommand(command="tip",         description="Tip a user 🎁"),
        BotCommand(command="profile",     description="My stats & VIP 👤"),
        BotCommand(command="missions",    description="Daily missions 📋"),
        BotCommand(command="fairness",    description="Provably fair 🔐"),
        BotCommand(command="cashout",     description="Cashout crash game 💸"),
        BotCommand(command="slots",       description="Play Slots 🎰"),
        BotCommand(command="help",        description="How to use guide 📖"),
        BotCommand(command="ping",        description="Bot status 📡"),
    ]
    group_commands = [
        BotCommand(command="balance",     description="Check your balance 💰"),
        BotCommand(command="deposit",     description="Deposit tokens 💳"),
        BotCommand(command="withdrawal",  description="Withdraw tokens 💸"),
        BotCommand(command="refer",       description="Referral program 🤝"),
        BotCommand(command="leaderboard", description="Top players 🏆"),
        BotCommand(command="tip",         description="Tip a user 🎁"),
        BotCommand(command="profile",     description="My stats & VIP 👤"),
        BotCommand(command="missions",    description="Daily missions 📋"),
        BotCommand(command="cashout",     description="Cashout crash 💸"),
        BotCommand(command="joinduel",    description="Join a PVP duel ⚔️"),
        BotCommand(command="help",        description="How to use guide 📖"),
    ]
    await bot.set_my_commands(private_commands, scope=BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(group_commands, scope=BotCommandScopeAllGroupChats())

    logger.info("🎰 Casino Bot started!")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())




# ═══════════════════════════════════════════════════════════════════════════════
# ─── VIP & RAKEBACK ───────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "menu_vip")
async def cb_vip(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Use /start first!", show_alert=True); return
    text = vip_profile_text(user)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=vip_menu_kb())
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=vip_menu_kb())
    await callback.answer()


@dp.callback_query(F.data == "menu_vip_levels")
async def cb_vip_levels(callback: CallbackQuery):
    text = vip_levels_info_text()
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_kb("menu_vip"))
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=back_kb("menu_vip"))
    await callback.answer()


@dp.callback_query(F.data == "menu_rakeback")
async def cb_rakeback(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Use /start first!", show_alert=True); return

    enabled = await db.get_setting("rakeback_enabled")
    if enabled != "1":
        await callback.answer("Rakeback is currently disabled.", show_alert=True); return

    vip = get_vip_level(user.get("total_wagered", 0))
    rb_weekly_rate = float(await db.get_setting("rakeback_weekly_pct") or "1")
    daily_amt = await calculate_daily_rakeback(user, vip, db.db_path)
    weekly_amt = await calculate_weekly_rakeback(user, rb_weekly_rate)
    can_d = await can_claim_daily(callback.from_user.id, db.db_path)
    can_w = await can_claim_weekly(callback.from_user.id, db.db_path)
    text = rakeback_menu_text(user, vip, daily_amt, weekly_amt, can_d, can_w, rb_weekly_rate)
    kb = rakeback_kb(can_d, can_w, daily_amt, weekly_amt)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@dp.callback_query(F.data.in_({"rb_claim_daily", "rb_claim_weekly"}))
async def cb_rb_claim(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Use /start first!", show_alert=True); return

    claim_type = "daily" if callback.data == "rb_claim_daily" else "weekly"
    vip = get_vip_level(user.get("total_wagered", 0))
    rb_weekly_rate = float(await db.get_setting("rakeback_weekly_pct") or "1")

    if claim_type == "daily":
        can = await can_claim_daily(callback.from_user.id, db.db_path)
        amount = await calculate_daily_rakeback(user, vip, db.db_path)
    else:
        can = await can_claim_weekly(callback.from_user.id, db.db_path)
        amount = await calculate_weekly_rakeback(user, rb_weekly_rate)

    if not can or amount <= 0:
        await callback.answer("Nothing to claim right now.", show_alert=True); return

    await db.update_token_balance(callback.from_user.id, amount)
    await db.add_transaction(callback.from_user.id, f"rakeback_{claim_type}", amount, "completed", "TOKEN")
    await record_claim(callback.from_user.id, claim_type, db.db_path)
    await callback.answer(f"♻️ Claimed {amount:,.4f} Tokens rakeback!", show_alert=True)
    # Refresh
    await cb_rakeback(callback)


# ═══════════════════════════════════════════════════════════════════════════════
# ─── DAILY MISSIONS ───────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "menu_missions")
async def cb_missions(callback: CallbackQuery):
    enabled = await db.get_setting("missions_enabled")
    if enabled != "1":
        await callback.answer("Missions are currently disabled.", show_alert=True); return
    user_id = callback.from_user.id
    prog = await db.get_mission_progress(user_id)
    import json
    claimed = json.loads(prog.get("claimed_missions", "[]"))
    claimable = claimable_missions(prog, claimed)
    claimable_ids = [m["id"] for m in claimable]
    text = missions_text(prog, claimed)
    kb = missions_kb(claimable_ids)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@dp.callback_query(F.data.startswith("mission_claim_"))
async def cb_mission_claim(callback: CallbackQuery):
    import json
    mission_id = callback.data.replace("mission_claim_", "")
    user_id = callback.from_user.id
    mission = next((m for m in MISSIONS if m["id"] == mission_id), None)
    if not mission:
        await callback.answer("Mission not found.", show_alert=True); return
    prog = await db.get_mission_progress(user_id)
    claimed = json.loads(prog.get("claimed_missions", "[]"))
    if mission_id in claimed:
        await callback.answer("Already claimed!", show_alert=True); return
    # Verify complete
    completed = prog.get(mission["type"], 0) >= mission["target"]
    if not completed:
        await callback.answer("Mission not complete yet.", show_alert=True); return
    # Grant reward
    claimed.append(mission_id)
    await db.update_mission_progress(user_id, claimed_missions=json.dumps(claimed))
    await db.update_token_balance(user_id, mission["reward"])
    await db.add_transaction(user_id, "mission_reward", mission["reward"], "completed", "TOKEN")
    await callback.answer(f"🎁 Claimed {mission['reward']} Tokens for {mission['name']}!", show_alert=True)
    await cb_missions(callback)


# ═══════════════════════════════════════════════════════════════════════════════
# ─── LOOTBOXES ────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "menu_lootbox")
async def cb_lootbox_menu(callback: CallbackQuery):
    enabled = await db.get_setting("lootbox_enabled")
    if enabled != "1":
        await callback.answer("Lootboxes are currently disabled.", show_alert=True); return
    text = cases_menu_text()
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=lootbox_kb())
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=lootbox_kb())
    await callback.answer()


@dp.callback_query(F.data.startswith("lootbox_open_"))
async def cb_lootbox_open(callback: CallbackQuery):
    case_key = callback.data.replace("lootbox_open_", "")
    case_info = get_case(case_key)
    if not case_info:
        await callback.answer("Case not found.", show_alert=True); return
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    if not user:
        await callback.answer("Use /start first!", show_alert=True); return
    price = case_info["price"]
    if user["token_balance"] < price:
        await callback.answer(f"Need {price:,} Tokens. You have {user['token_balance']:,.0f}.", show_alert=True)
        return
    await db.update_token_balance(user_id, -price)
    case, reward = open_case(case_key)
    # Grant reward
    if reward["type"] == "tokens":
        await db.update_token_balance(user_id, reward["amount"])
        await db.add_transaction(user_id, "lootbox_win", reward["amount"], "completed", "TOKEN")
        add_real_event(
            callback.from_user.first_name or str(user_id),
            f"{case['name']}",
            reward["amount"], "case"
        )
    await db.log_lootbox(user_id, case_key, reward["label"], reward["amount"])
    await db.add_transaction(user_id, "lootbox_purchase", price, "completed", "TOKEN")
    text = case_open_text(case, reward)
    new_bal = user["token_balance"] - price + (reward["amount"] if reward["type"] == "tokens" else 0)
    text += f"🪙 Balance: <b>{new_bal:,.4f}</b>"
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_kb("menu_lootbox"))
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=back_kb("menu_lootbox"))
    await callback.answer()


# ═══════════════════════════════════════════════════════════════════════════════
# ─── CRASH GAME ───────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
# ─── PVP DUELS ────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════


@dp.callback_query(F.data == "menu_pvp")
async def cb_pvp_menu(callback: CallbackQuery):
    try:
        await callback.message.edit_text(
            f"⚔️ <b>PVP DUELS</b>\n{SEP}\nChallenge other players!",
            parse_mode="HTML", reply_markup=pvp_menu_kb()
        )
    except:
        await callback.message.answer(
            f"⚔️ <b>PVP DUELS</b>\n{SEP}\nChallenge other players!",
            parse_mode="HTML", reply_markup=pvp_menu_kb()
        )
    await callback.answer()


@dp.callback_query(F.data.startswith("pvp_create_"))
async def cb_pvp_create(callback: CallbackQuery, state: FSMContext):
    game_type = callback.data.replace("pvp_create_", "")
    names = {"dice": "🎲 Dice Duel", "coinflip": "🪙 Coinflip Duel", "highroll": "🎯 High Roll"}
    await state.update_data(pvp_game_type=game_type)
    await state.set_state(PvpFSM.waiting_bet)
    await callback.message.answer(
        names.get(game_type, '⚔️') + f"\n{SEP}\nSend your bet amount in Tokens:",
        parse_mode="HTML", reply_markup=back_kb("menu_pvp")
    )
    await callback.answer()


@dp.message(PvpFSM.waiting_bet)
async def pvp_bet_input(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    game_type = data.get("pvp_game_type", "dice")
    try:
        bet = float(message.text.strip().replace(",", ""))
        if bet <= 0: raise ValueError
    except:
        await message.reply(error_text("❌ Invalid amount. Send a number."), parse_mode="HTML"); return
    user = await db.get_user(user_id)
    if not user or user["token_balance"] < bet:
        await message.reply(error_text(f"❌ Insufficient balance! You have {user['token_balance']:,.4f} Tokens."), parse_mode="HTML"); return
    house_fee = float(await db.get_setting("pvp_house_fee") or "5")
    duel_id = create_duel(user_id, message.from_user.first_name or str(user_id), game_type, bet, house_fee)
    await db.update_token_balance(user_id, -bet)
    text = duel_waiting_text(active_duels[duel_id])
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="⚔️ JOIN DUEL", callback_data=f"pvp_join_{duel_id}")
    await message.reply(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await state.clear()
    asyncio.create_task(auto_expire_duel(duel_id, 300))


@dp.callback_query(F.data.startswith("pvp_join_"))
async def cb_pvp_join(callback: CallbackQuery):
    duel_id = callback.data.replace("pvp_join_", "")
    user_id = callback.from_user.id
    duel = active_duels.get(duel_id)
    if not duel:
        await callback.answer("Duel expired or not found.", show_alert=True); return
    if duel["status"] != "waiting":
        await callback.answer("Duel already started or finished.", show_alert=True); return
    if duel["creator_id"] == user_id:
        await callback.answer("You cannot join your own duel.", show_alert=True); return
    user = await db.get_user(user_id)
    if not user or user["token_balance"] < duel["bet"]:
        await callback.answer(f"Need {duel['bet']:,.0f} Tokens to join.", show_alert=True); return
    # Lock opponent's bet
    await db.update_token_balance(user_id, -duel["bet"])
    join_duel(duel_id, user_id, callback.from_user.first_name or str(user_id))
    resolved = resolve_duel(duel_id)
    if not resolved:
        await callback.answer("Error resolving duel.", show_alert=True); return
    # Pay winner
    winner_id = resolved["winner_id"]
    net_prize = resolved["net_prize"]
    await db.update_token_balance(winner_id, net_prize)
    await db.add_transaction(winner_id, "pvp_win", net_prize, "completed", "TOKEN")
    loser_id = resolved["creator_id"] if winner_id == resolved["opponent_id"] else resolved["opponent_id"]
    await db.add_transaction(loser_id, "pvp_loss", resolved["bet"], "completed", "TOKEN")
    text = duel_result_text(resolved)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_main_kb())
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=back_to_main_kb())
    # Notify both
    try:
        other_id = resolved["creator_id"] if user_id == resolved["opponent_id"] else resolved["opponent_id"]
        await bot.send_message(other_id, text, parse_mode="HTML")
    except:
        pass
    await callback.answer()


@dp.callback_query(F.data == "pvp_list")
async def cb_pvp_list(callback: CallbackQuery):
    duels = get_open_duels()
    if not duels:
        await callback.answer("No open duels right now.", show_alert=True); return
    text = f"⚔️ <b>OPEN DUELS</b>\n{SEP}\n"
    for d in duels[:5]:
        text += f"• {d['creator_name']} — {d['game_type']} — {d['bet']:,.0f} T\n  Join: <code>/joinduel {d['id']}</code>\n"
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=pvp_menu_kb())
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=pvp_menu_kb())
    await callback.answer()


@dp.message(Command("joinduel"))
async def cmd_joinduel(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("Usage: <code>/joinduel &lt;duel_id&gt;</code>", parse_mode="HTML"); return
    duel_id = parts[1]
    user_id = message.from_user.id
    duel = active_duels.get(duel_id)
    if not duel:
        await message.reply(error_text("❌ Duel not found or expired."), parse_mode="HTML"); return
    if duel["status"] != "waiting":
        await message.reply(error_text("❌ Duel already started or finished."), parse_mode="HTML"); return
    if duel["creator_id"] == user_id:
        await message.reply(error_text("❌ You cannot join your own duel."), parse_mode="HTML"); return
    user = await db.get_user(user_id)
    if not user or user["token_balance"] < duel["bet"]:
        await message.reply(error_text(f"❌ Need {duel['bet']:,.0f} Tokens to join."), parse_mode="HTML"); return
    await db.update_token_balance(user_id, -duel["bet"])
    join_duel(duel_id, user_id, message.from_user.first_name or str(user_id))
    resolved = resolve_duel(duel_id)
    if not resolved:
        await message.reply(error_text("❌ Error resolving duel."), parse_mode="HTML"); return
    winner_id = resolved["winner_id"]
    net_prize = resolved["net_prize"]
    await db.update_token_balance(winner_id, net_prize)
    await db.add_transaction(winner_id, "pvp_win", net_prize, "completed", "TOKEN")
    loser_id = resolved["creator_id"] if winner_id == resolved["opponent_id"] else resolved["opponent_id"]
    await db.add_transaction(loser_id, "pvp_loss", resolved["bet"], "completed", "TOKEN")
    text = duel_result_text(resolved)
    await message.reply(text, parse_mode="HTML", reply_markup=back_to_main_kb())
    try:
        other_id = resolved["creator_id"]
        await bot.send_message(other_id, text, parse_mode="HTML")
    except:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# ─── RAIN ─────────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════


@dp.callback_query(F.data == "admin_rain")
async def cb_admin_rain(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS and not await db.is_sub_admin(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True); return
    await state.set_state(RainFSM.waiting_amount)
    await callback.message.answer(
        "🌧️ <b>SEND RAIN</b>\nSend rain amount in Tokens (e.g. 5000):",
        parse_mode="HTML", reply_markup=back_kb("admin_new_features")
    )
    await callback.answer()


@dp.message(RainFSM.waiting_amount)
async def rain_amount_input(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS and not await db.is_sub_admin(message.from_user.id):
        return
    try:
        amount = float(message.text.strip().replace(",", ""))
        if amount <= 0: raise ValueError
    except:
        await message.reply(error_text("❌ Invalid amount. Send a number."), parse_mode="HTML"); return
    await state.update_data(rain_amount=amount)
    await state.set_state(RainFSM.waiting_winners)
    await message.reply("How many max winners? (e.g. 20):", parse_mode="HTML")


@dp.message(RainFSM.waiting_winners)
async def rain_winners_input(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS and not await db.is_sub_admin(message.from_user.id):
        return
    try:
        winners = int(message.text.strip())
        if winners <= 0: raise ValueError
    except:
        await message.reply(error_text("❌ Invalid number. Send a whole number."), parse_mode="HTML"); return
    data = await state.get_data()
    amount = data["rain_amount"]
    await state.clear()
    rain = create_rain(amount, winners, duration_seconds=60, triggered_by="Admin")
    group_id = await db.get_setting("rain_group_id")
    text = rain_announce_text(rain)
    if group_id:
        try:
            await bot.send_message(int(group_id), text, parse_mode="HTML", reply_markup=rain_catch_kb())
        except:
            await message.reply(text, parse_mode="HTML", reply_markup=rain_catch_kb())
    else:
        await message.reply(text + "\n\n⚠️ No group set! Set rain_group_id in settings.", parse_mode="HTML", reply_markup=rain_catch_kb())
    await message.reply(
        "🌧️ Rain started!\n💰 Amount: " + f"{amount:,.0f}" + " Tokens\n👥 Max Winners: " + str(winners) + "\n⏳ Ends in 60 seconds",
        parse_mode="HTML"
    )
    asyncio.create_task(_finish_rain_task(amount, winners))


async def _finish_rain_task(amount: float, max_winners: int):
    await asyncio.sleep(60)
    rain = finish_rain()
    if not rain or not rain["participants"]:
        return
    share = rain["share_per_user"]
    for uid in rain["participants"]:
        await db.update_token_balance(uid, share)
        await db.add_transaction(uid, "rain_reward", share, "completed", "TOKEN")
        try:
            await bot.send_message(uid, success_text(f"🌧️ You caught rain! <b>+{share:,.4f} Tokens</b>"), parse_mode="HTML")
        except:
            pass


@dp.callback_query(F.data == "rain_catch")
async def cb_rain_catch(callback: CallbackQuery):
    enabled = await db.get_setting("rain_enabled")
    if enabled != "1":
        await callback.answer("Rain is disabled.", show_alert=True); return
    rain = get_active_rain()
    if not rain:
        await callback.answer("No active rain right now!", show_alert=True); return
    result = join_rain(callback.from_user.id)
    if result is None:
        if callback.from_user.id in rain.get("participants", set()):
            await callback.answer("You already caught this rain!", show_alert=True)
        else:
            await callback.answer("Rain is full!", show_alert=True)
        return
    count = len(rain["participants"])
    await callback.answer(f"🌧️ Caught! You are #{count}/{rain['max_winners']}", show_alert=True)


# ═══════════════════════════════════════════════════════════════════════════════
# ─── PROVABLY FAIR ────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════


@dp.message(Command("fairness", "verify", "provablyfair"))
async def cmd_provably_fair(message: Message):
    ss, cs, nonce = await get_or_create_seed_pair(message.from_user.id, db.db_path)
    text = provably_fair_info_text(hash_server_seed(ss), cs, nonce)
    await message.reply(text, parse_mode="HTML", reply_markup=provably_fair_kb())


@dp.callback_query(F.data == "pf_change_seed")
async def cb_pf_change_seed(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PfFSM.waiting_seed)
    await callback.message.answer(
        "🎯 Send your custom client seed (any text/numbers):\n"
        "Or send <code>auto</code> to generate one.",
        parse_mode="HTML", reply_markup=back_kb("menu_main")
    )
    await callback.answer()


@dp.message(PfFSM.waiting_seed)
async def pf_seed_input(message: Message, state: FSMContext):
    seed = message.text.strip()
    if seed.lower() == "auto":
        from provably_fair import generate_client_seed
        seed = generate_client_seed()
    await set_client_seed(message.from_user.id, seed[:64], db.db_path)
    await state.clear()
    ss, cs, nonce = await get_or_create_seed_pair(message.from_user.id, db.db_path)
    await message.reply(
        success_text(f"✅ Client seed updated!\n<code>{cs}</code>"),
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "pf_rotate")
async def cb_pf_rotate(callback: CallbackQuery):
    old_seed, new_hash = await rotate_server_seed(callback.from_user.id, db.db_path)
    await callback.message.answer(
        f"🔄 <b>Server Seed Rotated!</b>\n{SEP}\n"
        f"🔓 Revealed old seed:\n<code>{old_seed}</code>\n\n"
        f"🔒 New seed hash:\n<code>{new_hash}</code>\n\n"
        f"Use the revealed seed to verify your past results.",
        parse_mode="HTML"
    )
    await callback.answer()


# ═══════════════════════════════════════════════════════════════════════════════
# ─── PLAYER PROFILE ───────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "menu_profile")
async def cb_profile(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Use /start first!", show_alert=True); return
    vip = get_vip_level(user.get("total_wagered", 0))
    wagered = user.get("total_wagered", 0)
    wins = user.get("total_wins", 0)
    losses = user.get("total_losses", 0)
    total_games = wins + losses
    win_rate = (wins / total_games * 100) if total_games > 0 else 0
    biggest = user.get("biggest_win", 0)
    text = (
        f"👤 <b>PLAYER PROFILE</b>\n{SEP}\n"
        f"🏷️ Name: <b>{user.get('username') or callback.from_user.first_name}</b>\n"
        f"{vip['badge']} VIP: <b>{vip['name']}</b>\n"
        f"{SEP}\n"
        f"📊 <b>Stats</b>\n"
        f"🎮 Total Games: <b>{total_games}</b>\n"
        f"✅ Wins: <b>{wins}</b>\n"
        f"❌ Losses: <b>{losses}</b>\n"
        f"📈 Win Rate: <b>{win_rate:.1f}%</b>\n"
        f"💰 Total Wagered: <b>{wagered:,.0f} Tokens</b>\n"
        f"🏆 Biggest Win: <b>{biggest:,.4f} Tokens</b>\n"
        f"{SEP}\n"
        f"🪙 Balance: <b>{user['token_balance']:,.4f} Tokens</b>"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_kb("menu_main"))
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=back_kb("menu_main"))
    await callback.answer()


@dp.message(Command("missions", "quests"))
async def cmd_missions(message: Message):
    enabled = await db.get_setting("missions_enabled")
    if enabled != "1":
        await message.reply(error_text("❌ Missions are currently disabled."), parse_mode="HTML"); return
    import json
    user_id = message.from_user.id
    prog = await db.get_mission_progress(user_id)
    claimed = json.loads(prog.get("claimed_missions", "[]"))
    claimable = claimable_missions(prog, claimed)
    claimable_ids = [m["id"] for m in claimable]
    text = missions_text(prog, claimed)
    await message.reply(text, parse_mode="HTML", reply_markup=missions_kb(claimable_ids))


@dp.message(Command("profile", "stats", "me"))
async def cmd_profile(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.reply("Use /start first!"); return
    vip = get_vip_level(user.get("total_wagered", 0))
    wagered = user.get("total_wagered", 0)
    wins = user.get("total_wins", 0)
    losses = user.get("total_losses", 0)
    total_games = wins + losses
    win_rate = (wins / total_games * 100) if total_games > 0 else 0
    biggest = user.get("biggest_win", 0)
    text = (
        f"👤 <b>PLAYER PROFILE</b>\n{SEP}\n"
        f"{vip['badge']} VIP: <b>{vip['name']}</b>\n"
        f"✅ Wins: <b>{wins}</b> | ❌ Losses: <b>{losses}</b>\n"
        f"📈 Win Rate: <b>{win_rate:.1f}%</b>\n"
        f"💰 Wagered: <b>{wagered:,.0f} Tokens</b>\n"
        f"🏆 Biggest Win: <b>{biggest:,.4f} Tokens</b>\n"
        f"🪙 Balance: <b>{user['token_balance']:,.4f} Tokens</b>"
    )
    await message.reply(text, parse_mode="HTML")


# ═══════════════════════════════════════════════════════════════════════════════
# ─── LIVE FEED ────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "menu_feed")
async def cb_live_feed(callback: CallbackQuery):
    enabled = await db.get_setting("live_feed_enabled")
    if enabled != "1":
        await callback.answer("Live feed is currently disabled.", show_alert=True); return
    mix_fake = (await db.get_setting("live_feed_mix_fake")) == "1"
    text = feed_text(8, mix_fake)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_kb("menu_main"))
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=back_kb("menu_main"))
    await callback.answer()


# ═══════════════════════════════════════════════════════════════════════════════
# ─── ADMIN NEW FEATURES PANEL ─────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "admin_new_features")
async def cb_admin_new_features(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS and not await db.is_sub_admin(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True); return
    # Read current toggle states
    async def tog(key):
        v = await db.get_setting(key)
        return "🟢 ON" if v == "1" else "🔴 OFF"
    text = (
        f"🆕 <b>NEW FEATURES PANEL</b>\n{SEP}\n"
        f"💎 VIP System: {await tog('vip_enabled')}\n"
        f"♻️ Rakeback: {await tog('rakeback_enabled')}\n"
        f"📋 Missions: {await tog('missions_enabled')}\n"
        f"📦 Lootboxes: {await tog('lootbox_enabled')}\n"
        f"🚀 Crash Game: {await tog('crash_enabled')}\n"
        f"🎰 Slots: {await tog('slots_enabled')}\n"
        f"📡 Live Feed: {await tog('live_feed_enabled')}\n"
        f"🌧️ Rain: {await tog('rain_enabled')}\n"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_new_features_kb())
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=admin_new_features_kb())
    await callback.answer()


# Toggle handlers for new feature settings
import traceback

async def main():
    try:
        logger.info("🚀 Bot starting...")

        await db.init()

        await bot.delete_webhook(drop_pending_updates=True)


        from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats
        private_commands = [
            BotCommand(command="start",       description="Start the bot ✨"),
            BotCommand(command="balance",     description="Check your balance 💰"),
            BotCommand(command="deposit",     description="Deposit tokens 💳"),
            BotCommand(command="withdrawal",  description="Withdraw tokens 💸"),
            BotCommand(command="refer",       description="Referral program 🤝"),
            BotCommand(command="leaderboard", description="Top players 🏆"),
            BotCommand(command="tip",         description="Tip a user 🎁"),
            BotCommand(command="profile",     description="My stats & VIP 👤"),
            BotCommand(command="missions",    description="Daily missions 📋"),
            BotCommand(command="fairness",    description="Provably fair 🔐"),
            BotCommand(command="cashout",     description="Cashout crash 💸"),
            BotCommand(command="slots",       description="Play Slots 🎰"),
            BotCommand(command="help",        description="How to use guide 📖"),
            BotCommand(command="ping",        description="Bot status 📡"),
        ]
        group_commands = [
            BotCommand(command="balance",     description="Check your balance 💰"),
            BotCommand(command="deposit",     description="Deposit tokens 💳"),
            BotCommand(command="withdrawal",  description="Withdraw tokens 💸"),
            BotCommand(command="refer",       description="Referral program 🤝"),
            BotCommand(command="leaderboard", description="Top players 🏆"),
            BotCommand(command="tip",         description="Tip a user 🎁"),
            BotCommand(command="profile",     description="My stats & VIP 👤"),
            BotCommand(command="missions",    description="Daily missions 📋"),
            BotCommand(command="cashout",     description="Cashout crash 💸"),
            BotCommand(command="joinduel",    description="Join a PVP duel ⚔️"),
            BotCommand(command="help",        description="How to use guide 📖"),
        ]
        await bot.set_my_commands(private_commands, scope=BotCommandScopeAllPrivateChats())
        await bot.set_my_commands(group_commands, scope=BotCommandScopeAllGroupChats())
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("🎰 Casino Bot started!")
        await dp.start_polling(bot)

    except Exception as e:
        print("FATAL ERROR:", e)
        traceback.print_exc()


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



async def health_check(request):
    return web.Response(text="OK")


async def run_web():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health check running on port {port}")


if __name__ == "__main__":
    async def run_all():
        await asyncio.gather(main(), run_web())
    asyncio.run(run_all())
