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
    missions_main_kb, missions_period_kb,
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
from missions import ALL_MISSIONS, missions_text, claimable_missions, get_missions_by_period, get_mission_by_id, all_missions_summary, is_mission_complete, get_mission_progress as _mission_prog
from lootbox import open_case, cases_menu_text, case_open_text, get_case, CASES
from games.crash import run_crash_game, cashout_crash, active_crash_games, generate_crash_point
from games.slots import spin_reels, get_multiplier, slot_result_text, slots_help_text
from games.pvp import (
    create_duel, join_duel, resolve_duel, duel_result_text,
    duel_waiting_text, get_open_duels, cancel_duel, auto_expire_duel, active_duels,
    set_dice_roll, get_pending_duel_for_user, GAME_NAMES, GAME_EMOJIS, auto_expire_roll
)
from rain import create_rain, join_rain, finish_rain, rain_announce_text, rain_result_text, get_active_rain
from provably_fair import (
    get_or_create_seed_pair, increment_nonce, rotate_server_seed,
    set_client_seed, hash_server_seed, provably_fair_info_text
)
from activity_feed import add_real_event, feed_text
from live_leaderboard import start_loser_ticker, loser_leaderboard_text, add_real_loss, add_real_win
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
    "aset_pvp_group_id":        ("pvp_group_id", "Enter the Group Chat ID where PVP duel notifications will be sent:"),
    "aset_crash_min_bet":       ("crash_min_bet", "Enter minimum Crash bet in Tokens (e.g. 10):"),
    "aset_crash_max_bet":       ("crash_max_bet", "Enter maximum Crash bet in Tokens (e.g. 10000):"),
    "aset_slots_min_bet":       ("slots_min_bet", "Enter minimum Slots bet in Tokens (e.g. 10):"),
    "aset_slots_max_bet":       ("slots_max_bet", "Enter maximum Slots bet in Tokens (e.g. 5000):"),
    "aset_pvp_house_fee":       ("pvp_house_fee", "Enter PVP house fee % (e.g. 5):"),
    "aset_rakeback_weekly_pct": ("rakeback_weekly_pct", "Enter weekly rakeback % (e.g. 1):"),
    "aset_crash_win_pct":       ("crash_win_percent", "Enter Crash forced-win probability % (0 = off, 30 = 30% chance of winnable crash):"),
    "aset_slots_win_pct":       ("slots_win_percent", "Enter Slots forced-win probability % (0 = off, 20 = 20% guaranteed win spin):"),
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
    # Track login streak for missions
    await db.update_login_streak(user_id)
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
    """Main leaderboard — opens with Wagers / Lifetime by default."""
    fake = await db.get_fake_leaderboard()
    min_wager = float(await db.get_setting("leaderboard_min_wager") or "0")
    entries = await db.get_top_wagers("lifetime", 10)
    text = leaderboard_text(entries, "lifetime", fake, min_wager, section="wager")
    kb = leaderboard_kb(period="lifetime", section="wager")
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@dp.callback_query(F.data.startswith("lb_sec_"))
async def cb_lb_section(callback: CallbackQuery):
    """
    Switch between Win / Wager / Lose sections.
    callback.data format: lb_sec_{section}_{period}
    e.g. lb_sec_win_weekly  |  lb_sec_lose_lifetime
    """
    parts = callback.data.split("_")  # ['lb','sec','win','weekly']
    section = parts[2]                # 'win' | 'wager' | 'lose'
    period  = parts[3] if len(parts) > 3 else "lifetime"

    fake = await db.get_fake_leaderboard()
    min_wager = float(await db.get_setting("leaderboard_min_wager") or "0")

    if section == "wager":
        entries = await db.get_top_wagers(period, 10)
        text = leaderboard_text(entries, period, fake, min_wager, section="wager")
    elif section == "win":
        winners = await db.get_top_winners(period, 10)
        text = leaderboard_text([], period, fake, min_wager, winners=winners, section="win")
    else:  # lose
        losers = await db.get_top_losers(period, 10)
        text = leaderboard_text([], period, fake, min_wager, losers=losers, section="lose")

    kb = leaderboard_kb(period=period, section=section)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@dp.callback_query(F.data.startswith("lb_"))
async def cb_lb_filter(callback: CallbackQuery):
    """
    Switch period within current section.
    callback.data format: lb_{section}_{period}
    e.g. lb_wager_weekly  |  lb_win_daily  |  lb_lose_monthly
    Legacy format lb_{period} (without section) still works → defaults to wager.
    """
    raw = callback.data[3:]          # strip 'lb_'
    parts = raw.split("_")

    # Detect format: lb_wager_weekly vs legacy lb_weekly
    known_sections = ("wager", "win", "lose")
    if parts[0] in known_sections:
        section = parts[0]
        period  = parts[1] if len(parts) > 1 else "lifetime"
    else:
        section = "wager"
        period  = parts[0]

    fake = await db.get_fake_leaderboard()
    min_wager = float(await db.get_setting("leaderboard_min_wager") or "0")

    if section == "wager":
        entries = await db.get_top_wagers(period, 10)
        text = leaderboard_text(entries, period, fake, min_wager, section="wager")
    elif section == "win":
        winners = await db.get_top_winners(period, 10)
        text = leaderboard_text([], period, fake, min_wager, winners=winners, section="win")
    else:
        losers = await db.get_top_losers(period, 10)
        text = leaderboard_text([], period, fake, min_wager, losers=losers, section="lose")

    kb = leaderboard_kb(period=period, section=section)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


