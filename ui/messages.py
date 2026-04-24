from utils.helpers import format_date

SEP = "─" * 28


def main_menu_text(username: str, token_balance: float) -> str:
    return (
        f"🎰 *CASINO BOT*\n"
        f"{SEP}\n"
        f"👤 Player: *{username}*\n"
        f"🪙 Tokens: *{token_balance:,.4f}*\n"
        f"{SEP}\n"
        f"Choose an option below 👇"
    )


def wallet_text(user: dict) -> str:
    return (
        f"💰 *WALLET*\n"
        f"{SEP}\n"
        f"🪙 Token Balance: *{user['token_balance']:,.4f}*\n"
        f"📈 Total Wagered: *{user['total_wagered']:,.4f}* Tokens\n"
        f"🤝 Referral Earnings: *{user['referral_earnings']:,.4f}* Tokens\n"
        f"{SEP}"
    )


def referral_text(user: dict, ref_count: int, bot_username: str) -> str:
    link = f"https://t.me/{bot_username}?start=ref_{user['user_id']}"
    return (
        f"🤝 *REFERRAL PROGRAM*\n"
        f"{SEP}\n"
        f"🔗 Your Link:\n`{link}`\n\n"
        f"👥 Total Referrals: *{ref_count}*\n"
        f"🪙 Total Earned: *{user['referral_earnings']:,.4f}* Tokens\n"
        f"{SEP}"
    )


def bonus_text(user: dict, weekly: str, monthly: str, mode: str) -> str:
    eligible = "✅ Eligible" if user["bonus_eligible"] else "❌ Not Eligible"
    mode_txt = "Fixed" if mode == "fixed" else "Wager-based"
    return (
        f"🎁 *BONUS CENTER*\n"
        f"{SEP}\n"
        f"📊 Status: *{eligible}*\n"
        f"🎰 Mode: *{mode_txt}*\n\n"
        f"🗓️ Weekly Bonus: *{float(weekly):,.4f} Tokens*\n"
        f"📅 Monthly Bonus: *{float(monthly):,.4f} Tokens*\n"
        f"{SEP}"
    )


def game_result_text(game: str, won: bool, bet: float, reward: float, tax: float, new_balance: float, emoji: str) -> str:
    if won:
        return (
            f"{emoji} *{game.upper()} — YOU WON!*\n"
            f"{SEP}\n"
            f"🎯 Bet: *{bet:,.4f}* Tokens\n"
            f"🏆 Reward: *+{reward:,.4f}* Tokens\n"
            f"🧾 Tax (10%): *-{tax:,.4f}*\n"
            f"🪙 New Balance: *{new_balance:,.4f}*\n"
            f"{SEP}"
        )
    else:
        return (
            f"{emoji} *{game.upper()} — YOU LOST!*\n"
            f"{SEP}\n"
            f"🎯 Bet: *{bet:,.4f}* Tokens\n"
            f"💸 Lost: *-{bet:,.4f}*\n"
            f"🪙 New Balance: *{new_balance:,.4f}*\n"
            f"{SEP}"
        )


def error_text(msg: str) -> str:
    return f"❌ *Error*\n{SEP}\n{msg}\n{SEP}"


def success_text(msg: str) -> str:
    return f"✅ *Success*\n{SEP}\n{msg}\n{SEP}"


def history_text(txns: list) -> str:
    if not txns:
        return f"📋 *TRANSACTION HISTORY*\n{SEP}\nNo transactions found."
    lines = [f"📋 *TRANSACTION HISTORY*\n{SEP}"]
    type_emoji = {
        "bet": "🎯", "win": "🏆", "loss": "💸",
        "deposit": "💳", "withdraw": "💸", "referral": "🤝",
        "tip_sent": "💸", "tip_received": "🎁", "redeem": "🎟️",
        "crypto_deposit": "₿", "crypto_withdraw": "₿",
        "refund": "↩️", "admin_credit": "👑", "admin_debit": "🔻",
        "bonus": "🎁",
    }
    for t in txns:
        emoji = type_emoji.get(t["type"], "📌")
        sign = "+" if t["type"] in ("win", "deposit", "referral", "tip_received",
                                     "redeem", "crypto_deposit", "refund", "admin_credit", "bonus") else "-"
        lines.append(
            f"{emoji} *{t['type'].upper()}* | {sign}{t['amount']:,.4f} 🪙\n"
            f"   📅 {format_date(t['date'])}"
        )
    return "\n\n".join(lines)


def leaderboard_text(entries: list, period: str) -> str:
    period_names = {
        "daily": "📅 TODAY'S", "weekly": "📆 THIS WEEK'S",
        "monthly": "🗓️ THIS MONTH'S", "lifetime": "🏆 ALL-TIME"
    }
    title = period_names.get(period, "🏆")
    lines = [f"{title} TOP WAGERS\n{SEP}"]
    medals = ["🥇", "🥈", "🥉"]
    for i, u in enumerate(entries):
        medal = medals[i] if i < 3 else f"{i+1}."
        uname = u.get("username") or str(u["user_id"])
        lines.append(f"{medal} @{uname} — *{u['wagered']:,.4f}* Tokens")
    if not entries:
        lines.append("No data yet.")
    return "\n".join(lines)
