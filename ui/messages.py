from utils.helpers import format_balance, format_date

SEP = "─" * 28

def main_menu_text(username: str, balance: float) -> str:
    return (
        f"🎰 *CASINO BOT*\n"
        f"{SEP}\n"
        f"👤 Player: *{username}*\n"
        f"💰 Balance: *{format_balance(balance)}*\n"
        f"{SEP}\n"
        f"Choose an option below 👇"
    )


def wallet_text(user: dict) -> str:
    return (
        f"💰 *WALLET*\n"
        f"{SEP}\n"
        f"💵 Balance: *{format_balance(user['balance'])}*\n"
        f"📈 Total Wagered: *{format_balance(user['total_wagered'])}*\n"
        f"🤝 Referral Earnings: *{format_balance(user['referral_earnings'])}*\n"
        f"{SEP}"
    )


def referral_text(user: dict, ref_count: int, bot_username: str) -> str:
    link = f"https://t.me/{bot_username}?start=ref_{user['user_id']}"
    return (
        f"🤝 *REFERRAL PROGRAM*\n"
        f"{SEP}\n"
        f"🔗 Your Link:\n`{link}`\n\n"
        f"👥 Total Referrals: *{ref_count}*\n"
        f"💸 Total Earned: *{format_balance(user['referral_earnings'])}*\n"
        f"{SEP}\n"
        f"💡 Earn *0.01%* of every bet your referral places!\n"
        f"Lifetime passive income 🚀"
    )


def bonus_text(user: dict, weekly: str, monthly: str) -> str:
    eligible = "✅ Eligible" if user['bonus_eligible'] else "❌ Not Eligible"
    return (
        f"🎁 *BONUS CENTER*\n"
        f"{SEP}\n"
        f"📊 Status: *{eligible}*\n\n"
        f"🗓️ Weekly Bonus: *{format_balance(float(weekly))}*\n"
        f"📅 Monthly Bonus: *{format_balance(float(monthly))}*\n"
        f"{SEP}\n"
        f"📋 *How to be eligible:*\n"
        f"• Add bot username in your bio or name\n"
        f"• Account must be 7+ days old\n"
        f"• Contact support to claim"
    )


def game_result_text(game: str, won: bool, bet: float, reward: float, tax: float, new_balance: float, emoji: str) -> str:
    if won:
        return (
            f"{emoji} *{game.upper()} — YOU WON!*\n"
            f"{SEP}\n"
            f"🎯 Bet: *{format_balance(bet)}*\n"
            f"🏆 Reward: *+{format_balance(reward)}*\n"
            f"🧾 Tax (10%): *-{format_balance(tax)}*\n"
            f"💰 New Balance: *{format_balance(new_balance)}*\n"
            f"{SEP}"
        )
    else:
        return (
            f"{emoji} *{game.upper()} — YOU LOST!*\n"
            f"{SEP}\n"
            f"🎯 Bet: *{format_balance(bet)}*\n"
            f"💸 Lost: *-{format_balance(bet)}*\n"
            f"💰 New Balance: *{format_balance(new_balance)}*\n"
            f"{SEP}"
        )


def error_text(msg: str) -> str:
    return f"❌ *Error*\n{SEP}\n{msg}\n{SEP}"


def success_text(msg: str) -> str:
    return f"✅ *Success*\n{SEP}\n{msg}\n{SEP}"


def deposit_stars_text(star_id: str) -> str:
    return (
        f"⭐ *DEPOSIT VIA TELEGRAM STARS*\n"
        f"{SEP}\n"
        f"📋 Payment ID:\n`{star_id}`\n\n"
        f"📌 Steps:\n"
        f"1️⃣ Send stars to the above ID\n"
        f"2️⃣ Enter the amount below\n"
        f"3️⃣ Click 'I Have Paid'\n"
        f"4️⃣ Admin will verify & credit\n"
        f"{SEP}\n"
        f"⚠️ 5% processing fee applies\n"
        f"Please enter deposit amount (₹):"
    )


def deposit_upi_text(upi_id: str) -> str:
    return (
        f"🏦 *DEPOSIT VIA UPI*\n"
        f"{SEP}\n"
        f"💳 UPI ID:\n`{upi_id}`\n\n"
        f"📌 Steps:\n"
        f"1️⃣ Send money to above UPI\n"
        f"2️⃣ Take screenshot\n"
        f"3️⃣ Reply with: `amount txn_id`\n"
        f"   Example: `500 TXN123456`\n"
        f"{SEP}\n"
        f"⚠️ 5% processing fee applies"
    )


def history_text(txns: list) -> str:
    if not txns:
        return f"📋 *TRANSACTION HISTORY*\n{SEP}\nNo transactions found."
    lines = [f"📋 *TRANSACTION HISTORY*\n{SEP}"]
    type_emoji = {
        "bet": "🎯", "win": "🏆", "loss": "💸",
        "deposit": "💳", "withdraw": "💸", "referral": "🤝"
    }
    for t in txns:
        emoji = type_emoji.get(t['type'], "📌")
        sign = "+" if t['type'] in ("win", "deposit", "referral") else "-"
        lines.append(
            f"{emoji} *{t['type'].upper()}* | {sign}₹{t['amount']:,.2f}\n"
            f"   📅 {format_date(t['date'])}"
        )
    return "\n\n".join(lines)
