from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Dict


def main_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎮 Play Games", callback_data="menu_games"),
        InlineKeyboardButton(text="💰 Wallet", callback_data="menu_wallet")
    )
    builder.row(
        InlineKeyboardButton(text="🎁 Bonus", callback_data="menu_bonus"),
        InlineKeyboardButton(text="🤝 Referral", callback_data="menu_referral")
    )
    builder.row(
        InlineKeyboardButton(text="💎 VIP & Rakeback", callback_data="menu_vip"),
        InlineKeyboardButton(text="📋 Missions", callback_data="menu_missions")
    )
    builder.row(
        InlineKeyboardButton(text="📦 Lootboxes", callback_data="menu_lootbox"),
        InlineKeyboardButton(text="📡 Live Feed", callback_data="menu_feed")
    )
    builder.row(
        InlineKeyboardButton(text="🆘 Support", callback_data="menu_support"),
        InlineKeyboardButton(text="📊 History", callback_data="menu_history")
    )
    builder.row(
        InlineKeyboardButton(text="🎟️ Redeem", callback_data="menu_redeem"),
        InlineKeyboardButton(text="🏆 Leaderboard", callback_data="menu_leaderboard")
    )
    builder.row(
        InlineKeyboardButton(text="👤 My Profile", callback_data="menu_profile"),
        InlineKeyboardButton(text="❓ Help", callback_data="menu_help")
    )
    if is_admin:
        builder.row(InlineKeyboardButton(text="🔐 Admin Panel", callback_data="admin_panel"))
    return builder.as_markup()


def games_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎲 Dice", callback_data="game_dice"),
        InlineKeyboardButton(text="🚀 Crash", callback_data="game_crash")
    )
    builder.row(
        InlineKeyboardButton(text="🎰 Slots", callback_data="game_slots"),
        InlineKeyboardButton(text="🪙 Coin Flip", callback_data="game_coinflip")
    )
    builder.row(
        InlineKeyboardButton(text="💣 Mines", callback_data="game_mines"),
    )
    builder.row(
        InlineKeyboardButton(text="🏀 Basketball", callback_data="game_bask"),
        InlineKeyboardButton(text="⚽ Soccer", callback_data="game_ball")
    )
    builder.row(
        InlineKeyboardButton(text="🎳 Bowling", callback_data="game_bowl"),
        InlineKeyboardButton(text="🎯 Darts", callback_data="game_darts")
    )
    builder.row(
        InlineKeyboardButton(text="🚀 Limbo", callback_data="game_limbo"),
        InlineKeyboardButton(text="⚔️ PVP Duel", callback_data="menu_pvp")
    )
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="menu_main"))
    return builder.as_markup()


def wallet_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💳 Deposit", callback_data="wallet_deposit"),
        InlineKeyboardButton(text="💸 Withdraw", callback_data="wallet_withdraw")
    )
    builder.row(
        InlineKeyboardButton(text="📋 History", callback_data="menu_history"),
        InlineKeyboardButton(text="🔙 Back", callback_data="menu_main")
    )
    return builder.as_markup()


def deposit_method_kb() -> InlineKeyboardMarkup:
    """Top-level deposit: choose INR, Stars, or Auto Crypto."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏦 UPI (INR)", callback_data="deposit_upi"),
        InlineKeyboardButton(text="⭐ Stars", callback_data="deposit_stars")
    )
    builder.row(
        InlineKeyboardButton(text="₿ Crypto (Auto)", callback_data="deposit_crypto_auto")
    )
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="menu_wallet"))
    return builder.as_markup()


def withdraw_method_kb(cryptos: List[Dict]) -> InlineKeyboardMarkup:
    """Withdraw: UPI or crypto (single button → currency select)."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏦 UPI Withdrawal", callback_data="withdraw_upi"))
    if cryptos:
        builder.row(InlineKeyboardButton(text="₿ Crypto Withdrawal", callback_data="withdraw_crypto_select"))
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="menu_wallet"))
    return builder.as_markup()


def oxapay_currency_kb(token_amount: float) -> InlineKeyboardMarkup:
    """Choose crypto for Oxapay auto-deposit."""
    builder = InlineKeyboardBuilder()
    currencies = [
        ("USDT (TRC20)", "USDT", "TRC20"),
        ("USDT (ERC20)", "USDT", "ERC20"),
        ("USDT (BEP20)", "USDT", "BEP20"),
        ("Bitcoin",      "BTC",  "BTC"),
        ("Ethereum",     "ETH",  "ERC20"),
        ("Litecoin",     "LTC",  "LTC"),
        ("TRON",         "TRX",  "TRC20"),
        ("Dogecoin",     "DOGE", "DOGE"),
        ("BNB",          "BNB",  "BEP20"),
    ]
    for label, currency, network in currencies:
        builder.row(InlineKeyboardButton(
            text=f"₿ {label}",
            callback_data=f"oxapay_{currency}_{network}_{int(token_amount)}"
        ))
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="wallet_deposit"))
    return builder.as_markup()


def back_to_main_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏠 Main Menu", callback_data="menu_main"),
        InlineKeyboardButton(text="🎮 Play Again", callback_data="menu_games")
    )
    return builder.as_markup()


def back_kb(callback: str = "menu_main") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data=callback))
    return builder.as_markup()




def admin_panel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💳 Deposits", callback_data="admin_deposits"),
        InlineKeyboardButton(text="💸 Withdrawals", callback_data="admin_withdrawals")
    )
    builder.row(
        InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast"),
        InlineKeyboardButton(text="📊 Stats", callback_data="admin_stats")
    )
    builder.row(
        InlineKeyboardButton(text="🎟️ Redeem Codes", callback_data="admin_redeems"),
        InlineKeyboardButton(text="⚙️ Settings", callback_data="admin_settings")
    )
    builder.row(
        InlineKeyboardButton(text="🏆 Wager Board", callback_data="admin_wager"),
        InlineKeyboardButton(text="👤 User Lookup", callback_data="admin_user_lookup")
    )
    builder.row(
        InlineKeyboardButton(text="👮 Sub Admins", callback_data="admin_sub_admins"),
        InlineKeyboardButton(text="🏆 Fake Leaderboard", callback_data="admin_fake_lb")
    )
    builder.row(
        InlineKeyboardButton(text="💡 Tip User", callback_data="admin_tip_btn"),
        InlineKeyboardButton(text="♻️ Regen Code", callback_data="admin_regen_code")
    )
    builder.row(InlineKeyboardButton(text="🆕 New Features", callback_data="admin_new_features"))
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="menu_main"))
    return builder.as_markup()


def admin_settings_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏦 UPI ID", callback_data="aset_upi"),
        InlineKeyboardButton(text="📸 UPI QR", callback_data="aset_qr")
    )
    builder.row(
        InlineKeyboardButton(text="📥 Deposit Tax %", callback_data="aset_deptax"),
        InlineKeyboardButton(text="📤 Withdraw Tax %", callback_data="aset_wdtax")
    )
    builder.row(
        InlineKeyboardButton(text="💲 USD→Token Rate", callback_data="aset_usd_token_rate"),
        InlineKeyboardButton(text="💱 INR→Token Rate", callback_data="aset_inr_token_rate"),
    )
    builder.row(
        InlineKeyboardButton(text="⭐ Stars→Token Rate", callback_data="aset_stars_token_rate"),
        InlineKeyboardButton(text="🔑 Oxapay Key", callback_data="aset_oxapay_key"),
    )
    builder.row(
        InlineKeyboardButton(text="🎁 Weekly Bonus", callback_data="aset_weekly"),
        InlineKeyboardButton(text="📅 Monthly Bonus", callback_data="aset_monthly")
    )
    builder.row(
        InlineKeyboardButton(text="🎰 Bonus Mode", callback_data="aset_bonusmode"),
        InlineKeyboardButton(text="🏷️ Bot Tag", callback_data="aset_bottag")
    )
    builder.row(
        InlineKeyboardButton(text="💸 Min Withdraw", callback_data="aset_minwd"),
        InlineKeyboardButton(text="🔄 Toggle Withdraw", callback_data="aset_wdtoggle")
    )
    builder.row(
        InlineKeyboardButton(text="🤝 Referral %", callback_data="aset_referral"),
        InlineKeyboardButton(text="💸 Game Tax %", callback_data="aset_gametax"),
    )
    builder.row(
        InlineKeyboardButton(text="🚀 Limbo Win %", callback_data="aset_limbopct"),
        InlineKeyboardButton(text="🏆 LB Min Wager", callback_data="aset_lb_min_wager"),
    )
    builder.row(
        InlineKeyboardButton(text="💸 User Tip Toggle", callback_data="aset_user_tip_toggle"),
        InlineKeyboardButton(text="⬇️ Tip Min", callback_data="aset_user_tip_min"),
    )
    builder.row(
        InlineKeyboardButton(text="⬆️ Tip Max", callback_data="aset_user_tip_max"),
    )
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="admin_panel"))
    return builder.as_markup()


def admin_crypto_kb(cryptos: List[Dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for c in cryptos:
        status = "🟢" if c["enabled"] else "🔴"
        builder.row(InlineKeyboardButton(
            text=f"{status} {c['symbol']} ({c['network']})",
            callback_data=f"admin_crypto_detail_{c['symbol']}"
        ))
    builder.row(InlineKeyboardButton(text="➕ Add Crypto", callback_data="admin_crypto_add"))
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="admin_panel"))
    return builder.as_markup()


def admin_crypto_detail_kb(symbol: str, enabled: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    toggle_text = "🔴 Disable" if enabled else "🟢 Enable"
    builder.row(
        InlineKeyboardButton(text=toggle_text, callback_data=f"admin_crypto_toggle_{symbol}"),
        InlineKeyboardButton(text="✏️ Update Address", callback_data=f"admin_crypto_addr_{symbol}")
    )
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="admin_crypto"))
    return builder.as_markup()


def approve_reject_deposit_kb(did: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Approve", callback_data=f"dep_approve_{did}"),
        InlineKeyboardButton(text="❌ Reject", callback_data=f"dep_reject_{did}")
    )
    return builder.as_markup()


def approve_reject_withdraw_kb(wid: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Approve & Pay", callback_data=f"wd_approve_{wid}"),
        InlineKeyboardButton(text="❌ Reject", callback_data=f"wd_reject_{wid}")
    )
    return builder.as_markup()


def upi_paid_done_kb(did: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Payment Done", callback_data=f"upi_done_{did}"))
    builder.row(InlineKeyboardButton(text="❌ Cancel", callback_data="menu_wallet"))
    return builder.as_markup()


def bonus_claim_kb(can_weekly: bool, can_monthly: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if can_weekly:
        builder.row(InlineKeyboardButton(text="🗓️ Claim Weekly Bonus", callback_data="bonus_claim_weekly"))
    if can_monthly:
        builder.row(InlineKeyboardButton(text="📅 Claim Monthly Bonus", callback_data="bonus_claim_monthly"))
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="menu_main"))
    return builder.as_markup()


def redeem_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎟️ Enter Code", callback_data="redeem_enter"))
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="menu_main"))
    return builder.as_markup()


def leaderboard_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 Daily", callback_data="lb_daily"),
        InlineKeyboardButton(text="📆 Weekly", callback_data="lb_weekly"),
    )
    builder.row(
        InlineKeyboardButton(text="🗓️ Monthly", callback_data="lb_monthly"),
        InlineKeyboardButton(text="🏆 Lifetime", callback_data="lb_lifetime"),
    )
    builder.row(InlineKeyboardButton(text="💀 Loser Board", callback_data="menu_loser_board"))
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="menu_main"))
    return builder.as_markup()


def admin_wager_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 Today", callback_data="awager_daily"),
        InlineKeyboardButton(text="📆 This Week", callback_data="awager_weekly"),
    )
    builder.row(
        InlineKeyboardButton(text="🗓️ This Month", callback_data="awager_monthly"),
        InlineKeyboardButton(text="🏆 All Time", callback_data="awager_lifetime"),
    )
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="admin_panel"))
    return builder.as_markup()


def admin_user_action_kb(user_id: int, is_banned: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    ban_text = "🔓 Unban" if is_banned else "🚫 Ban"
    builder.row(
        InlineKeyboardButton(text="➕ Add Tokens", callback_data=f"auser_add_{user_id}"),
        InlineKeyboardButton(text="➖ Remove Tokens", callback_data=f"auser_remove_{user_id}")
    )
    builder.row(
        InlineKeyboardButton(text="⚖️ Set Tokens", callback_data=f"auser_set_{user_id}"),
        InlineKeyboardButton(text=ban_text, callback_data=f"auser_ban_{user_id}")
    )
    builder.row(
        InlineKeyboardButton(text="📥 Set Dep Tax", callback_data=f"auser_deptax_{user_id}"),
        InlineKeyboardButton(text="📤 Set WD Tax", callback_data=f"auser_wdtax_{user_id}")
    )
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="admin_user_lookup"))
    return builder.as_markup()


def support_reply_kb(ticket_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="↩️ Reply to User",
        callback_data=f"support_reply_{ticket_id}"
    ))
    return builder.as_markup()
    


def vip_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="♻️ Rakeback", callback_data="menu_rakeback"))
    builder.row(InlineKeyboardButton(text="💎 VIP Levels Info", callback_data="menu_vip_levels"))
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="menu_main"))
    return builder.as_markup()


def rakeback_kb(can_daily: bool, can_weekly: bool, daily_amt: float, weekly_amt: float) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if can_daily and daily_amt > 0:
        builder.row(InlineKeyboardButton(text=f"📅 Claim Daily ({daily_amt:,.2f})", callback_data="rb_claim_daily"))
    if can_weekly and weekly_amt > 0:
        builder.row(InlineKeyboardButton(text=f"📆 Claim Weekly ({weekly_amt:,.2f})", callback_data="rb_claim_weekly"))
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="menu_vip"))
    return builder.as_markup()


def missions_kb(claimable_ids: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for mid in claimable_ids:
        builder.row(InlineKeyboardButton(text=f"🎁 Claim: {mid}", callback_data=f"mission_claim_{mid}"))
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="menu_main"))
    return builder.as_markup()


def lootbox_kb() -> InlineKeyboardMarkup:
    from lootbox import get_cases_sync
    cases = get_cases_sync()
    builder = InlineKeyboardBuilder()
    for key, case in cases.items():
        builder.row(InlineKeyboardButton(
            text=f"{case['icon']} {case['name']} — {case['price']:,} T",
            callback_data=f"lootbox_open_{key}"
        ))
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="menu_main"))
    return builder.as_markup()


def coinflip_choice_kb(amount: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👑 Heads", callback_data=f"cf_pick_heads_{amount}"),
        InlineKeyboardButton(text="🦅 Tails", callback_data=f"cf_pick_tails_{amount}"),
    )
    builder.row(InlineKeyboardButton(text="❌ Cancel", callback_data="menu_games"))
    return builder.as_markup()


def admin_lootbox_cases_kb(cases: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, case in cases.items():
        builder.row(InlineKeyboardButton(
            text=f"{case['icon']} {case['name']} ({case['price']:,}T)",
            callback_data=f"admin_lb_edit_{key}"
        ))
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="admin_new_features"))
    return builder.as_markup()


def admin_lootbox_case_edit_kb(case_key: str, case: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💰 Set Price", callback_data=f"admin_lb_price_{case_key}"))
    for i, r in enumerate(case["rewards"]):
        builder.row(InlineKeyboardButton(
            text=f"✏️ Reward {i+1}: {r['label']} (w:{r['weight']})",
            callback_data=f"admin_lb_reward_{case_key}_{i}"
        ))
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="admin_lootbox_panel"))
    return builder.as_markup()


def admin_vip_levels_kb(levels: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for lvl in levels:
        builder.row(InlineKeyboardButton(
            text=f"{lvl['badge']} {lvl['name']} (Lv{lvl['level']})",
            callback_data=f"admin_vip_edit_{lvl['level']}"
        ))
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="admin_new_features"))
    return builder.as_markup()


def admin_vip_level_edit_kb(level_idx: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📊 Min Wager",          callback_data=f"admin_vip_wager_{level_idx}"))
    builder.row(InlineKeyboardButton(text="💸 WD Tax Discount %",  callback_data=f"admin_vip_wddisc_{level_idx}"))
    builder.row(InlineKeyboardButton(text="📥 Dep Tax Discount %", callback_data=f"admin_vip_depdisc_{level_idx}"))
    builder.row(InlineKeyboardButton(text="♻️ Rakeback %",          callback_data=f"admin_vip_rakeback_{level_idx}"))
    builder.row(InlineKeyboardButton(text="🎁 Bonus Multiplier",   callback_data=f"admin_vip_mult_{level_idx}"))
    builder.row(InlineKeyboardButton(text="🔙 Back",               callback_data="admin_vip_panel"))
    return builder.as_markup()


def crash_bet_kb(bet: float) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💸 Cashout NOW", callback_data=f"crash_cashout"))
    return builder.as_markup()


def crash_autocashout_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for mult in [1.5, 2.0, 3.0, 5.0, 10.0]:
        builder.row(InlineKeyboardButton(text=f"⚡ Auto {mult}x", callback_data=f"crash_auto_{mult}"))
    builder.row(InlineKeyboardButton(text="▶️ No Auto (Manual)", callback_data="crash_auto_0"))
    builder.row(InlineKeyboardButton(text="❌ Cancel", callback_data="menu_games"))
    return builder.as_markup()


def pvp_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎲 Dice Duel", callback_data="pvp_create_dice"))
    builder.row(InlineKeyboardButton(text="🎯 High Roll", callback_data="pvp_create_highroll"))
    builder.row(InlineKeyboardButton(text="👀 Open Duels", callback_data="pvp_list"))
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="menu_games"))
    return builder.as_markup()


def pvp_join_kb(duel_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⚔️ JOIN DUEL", callback_data=f"pvp_join_{duel_id}"))
    return builder.as_markup()


def rain_catch_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🌧️ CATCH RAIN!", callback_data="rain_catch"))
    return builder.as_markup()


def provably_fair_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎯 Change Client Seed", callback_data="pf_change_seed"))
    builder.row(InlineKeyboardButton(text="🔄 Rotate Server Seed", callback_data="pf_rotate"))
    builder.row(InlineKeyboardButton(text="✅ Verify Last Result", callback_data="pf_verify"))
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="menu_main"))
    return builder.as_markup()


def admin_new_features_kb() -> InlineKeyboardMarkup:
    """Admin controls for all new features."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🌧️ Send Rain", callback_data="admin_rain"),
        InlineKeyboardButton(text="💎 VIP Toggle", callback_data="aset_vip_enabled"),
    )
    builder.row(
        InlineKeyboardButton(text="♻️ Rakeback Toggle", callback_data="aset_rakeback_enabled"),
        InlineKeyboardButton(text="📋 Missions Toggle", callback_data="aset_missions_enabled"),
    )
    builder.row(
        InlineKeyboardButton(text="📦 Lootbox Toggle", callback_data="aset_lootbox_enabled"),
        InlineKeyboardButton(text="🚀 Crash Toggle", callback_data="aset_crash_enabled"),
    )
    builder.row(
        InlineKeyboardButton(text="🎰 Slots Toggle", callback_data="aset_slots_enabled"),
        InlineKeyboardButton(text="⚔️ PVP Fee %", callback_data="aset_pvp_house_fee"),
    )
    builder.row(
        InlineKeyboardButton(text="♻️ Weekly RB %", callback_data="aset_rakeback_weekly_pct"),
        InlineKeyboardButton(text="📡 Feed Toggle", callback_data="aset_live_feed_enabled"),
    )
    builder.row(
        InlineKeyboardButton(text="🌧️ Rain Group ID", callback_data="aset_rain_group_id"),
        InlineKeyboardButton(text="⚔️ PVP Group ID", callback_data="aset_pvp_group_id"),
    )
    builder.row(
        InlineKeyboardButton(text="🎲 Crash Min Bet", callback_data="aset_crash_min_bet"),
        InlineKeyboardButton(text="🎲 Crash Max Bet", callback_data="aset_crash_max_bet"),
        InlineKeyboardButton(text="🎰 Slots Min Bet", callback_data="aset_slots_min_bet"),
    )
    builder.row(
        InlineKeyboardButton(text="🎰 Slots Max Bet", callback_data="aset_slots_max_bet"),
    )
    builder.row(
        InlineKeyboardButton(text="💥 Crash House Edge %", callback_data="aset_crash_house_edge"),
        InlineKeyboardButton(text="🎰 Slots Win %", callback_data="aset_slots_win_pct"),
    )
    builder.row(
        InlineKeyboardButton(text="🚀 Crash Win Tax %", callback_data="aset_crash_win_tax"),
    )
    builder.row(
        InlineKeyboardButton(text="💣 Mines Min Mines", callback_data="aset_mines_min"),
        InlineKeyboardButton(text="💣 Mines Max Mines", callback_data="aset_mines_max"),
    )
    builder.row(
        InlineKeyboardButton(text="💣 Mines House Edge %", callback_data="aset_mines_edge"),
        InlineKeyboardButton(text="💣 Mines Win % ", callback_data="aset_mines_winpct"),
    )
    builder.row(
        InlineKeyboardButton(text="💀 Loser Board Toggle", callback_data="aset_loser_board_enabled"),
        InlineKeyboardButton(text="📋 Mission Control", callback_data="admin_missions_panel"),
    )
    builder.row(
        InlineKeyboardButton(text="📦 Lootbox Config", callback_data="admin_lootbox_panel"),
        InlineKeyboardButton(text="💎 VIP Level Config", callback_data="admin_vip_panel"),
    )
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="admin_panel"))
    return builder.as_markup()


def mines_count_kb(bet: float) -> InlineKeyboardMarkup:
    """Choose number of mines (min 5)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="5 💣", callback_data=f"mines_start_{bet}_5"),
        InlineKeyboardButton(text="7 💣", callback_data=f"mines_start_{bet}_7"),
        InlineKeyboardButton(text="10 💣", callback_data=f"mines_start_{bet}_10"),
        InlineKeyboardButton(text="15 💣", callback_data=f"mines_start_{bet}_15"),
    )
    builder.row(
        InlineKeyboardButton(text="20 💣", callback_data=f"mines_start_{bet}_20"),
        InlineKeyboardButton(text="23 💣", callback_data=f"mines_start_{bet}_23"),
    )
    builder.row(InlineKeyboardButton(text="❌ Cancel", callback_data="menu_games"))
    return builder.as_markup()


def mines_grid_kb(bet: float, mines: int, revealed: list, game_id: str, cashed_out: bool = False) -> InlineKeyboardMarkup:
    """5x5 grid — revealed tiles shown, rest are hidden."""
    builder = InlineKeyboardBuilder()
    for i in range(25):
        if i in revealed:
            r = revealed[revealed.index(i)] if isinstance(revealed[0], int) else i
            builder.button(text="✅", callback_data=f"mines_tile_{game_id}_{i}")
        else:
            builder.button(text="⬜", callback_data=f"mines_tile_{game_id}_{i}")
    builder.adjust(5)
    if not cashed_out:
        builder.row(InlineKeyboardButton(text="💰 CASHOUT", callback_data=f"mines_cashout_{game_id}"))
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="menu_games"))
    return builder.as_markup()

