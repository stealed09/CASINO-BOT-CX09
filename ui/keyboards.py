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
        InlineKeyboardButton(text="🆘 Support", callback_data="menu_support"),
        InlineKeyboardButton(text="📊 History", callback_data="menu_history")
    )
    builder.row(
        InlineKeyboardButton(text="🎟️ Redeem Code", callback_data="menu_redeem"),
        InlineKeyboardButton(text="🏆 Leaderboard", callback_data="menu_leaderboard")
    )
    if is_admin:
        builder.row(InlineKeyboardButton(text="🔐 Admin Panel", callback_data="admin_panel"))
    return builder.as_markup()


def games_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎲 Dice", callback_data="game_dice"),
        InlineKeyboardButton(text="🏀 Basketball", callback_data="game_bask")
    )
    builder.row(
        InlineKeyboardButton(text="⚽ Soccer", callback_data="game_ball"),
        InlineKeyboardButton(text="🎳 Bowling", callback_data="game_bowl")
    )
    builder.row(
        InlineKeyboardButton(text="🎯 Darts", callback_data="game_darts"),
        InlineKeyboardButton(text="🚀 Limbo", callback_data="game_limbo")
    )
    builder.row(InlineKeyboardButton(text="🪙 Coin Flip /cf", callback_data="game_coinflip"))
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
    """Withdraw: UPI or crypto."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏦 UPI Withdrawal", callback_data="withdraw_upi"))
    for c in cryptos:
        builder.row(InlineKeyboardButton(
            text=f"₿ {c['symbol']} ({c['network']})",
            callback_data=f"withdraw_crypto_{c['symbol']}"
        ))
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


def coinflip_choice_kb(amount: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👑 Heads", callback_data=f"cf_heads_{amount}"),
        InlineKeyboardButton(text="🦅 Tails", callback_data=f"cf_tails_{amount}")
    )
    builder.row(InlineKeyboardButton(text="❌ Cancel", callback_data="menu_games"))
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
        InlineKeyboardButton(text="₿ Crypto Manager", callback_data="admin_crypto"),
        InlineKeyboardButton(text="👮 Sub Admins", callback_data="admin_sub_admins")
    )
    builder.row(
        InlineKeyboardButton(text="🏆 Fake Leaderboard", callback_data="admin_fake_lb"),
        InlineKeyboardButton(text="💡 Tip User", callback_data="admin_tip_btn")
    )
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
        InlineKeyboardButton(text="🔑 Oxapay Key", callback_data="aset_oxapay_key"),
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
    
