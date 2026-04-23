from utils.helpers import format_date

SEP = "─" * 28


def format_amount(amount: float, currency: str = "INR") -> str:
    if currency.upper() == "INR":
        return f"₹{amount:,.2f}"
    return f"{amount:.6f} {currency.upper()}"


def format_balance(amount: float) -> str:
    return f"₹{amount:,.2f}"


def main_menu_text(username: str, balance: float, currency_mode: str = "inr",
                   crypto_balances: list = None) -> str:
    if currency_mode == "inr":
        bal_line = f"💰 Balance: *₹{balance:,.2f}*"
    else:
        bal_line = f"💰 INR Balance: *₹{balance:,.2f}*"
        if crypto_balances:
            for cb in crypto_balances:
                if cb["balance"] > 0:
                    bal_line += f"\n₿ {cb['symbol']}: *{cb['balance']:.6f}*"
    return (
        f"🎰 *CASINO BOT*\n"
        f"{SEP}\n"
        f"👤 Player: *{username}*\n"
        f"{bal_line}\n"
        f"🌐 Mode: *{'₹ INR' if currency_mode == 'inr' else '₿ CRYPTO'}*\n"
        f"{SEP}\n"
        f"Choose an option below 👇"
    )


def wallet_inr_text(user: dict) -> str:
    return (
        f"💰 *INR WALLET*\n"
        f"{SEP}\n"
        f"💵 Balance: *₹{user['balance']:,.2f}*\n"
        f"📈 Total Wagered: *₹{user['total_wagered']:,.2f}*\n"
        f"🤝 Referral Earnings: *₹{user['referral_earnings']:,.2f}*\n"
        f"{SEP}"
    )


def wallet_crypto_text(user: dict, crypto_balances: list) -> str:
    lines = [f"₿ *CRYPTO WALLET*\n{SEP}"]
    if crypto_balances:
        for cb in crypto_balances:
            lines.append(f"• *{cb['symbol']}*: `{cb['balance']:.6f}`")
    else:
        lines.append("No crypto balance yet.")
    lines.append(f"\n💵 INR Balance: *₹{user['balance']:,.2f}*")
    lines.append(SEP)
    return "\n".join(lines)


def referral_text(user: dict, ref_count: int, bot_username: str) -> str:
    link = f"https://t.me/{bot_username}?start=ref_{user['user_id']}"
    return (
        f"🤝 *REFERRAL PROGRAM*\n"
        f"{SEP}\n"
        f"🔗 Your Link:\n`{link}`\n\n"
        f"👥 Total Referrals: *{ref_count}*\n"
        f"💸 Total Earned: *₹{user['referral_earnings']:,.2f}*\n"
        f"{SEP}"
    )


def bonus_text(user: dict, weekly: str, monthly: str) -> str:
    eligible = "✅ Eligible" if user['bonus_eligible'] else "❌ Not Eligible"
    return (
        f"🎁 *BONUS CENTER*\n"
        f"{SEP}\n"
        f"📊 Status: *{eligible}*\n\n"
        f"🗓️ Weekly Bonus: *₹{float(weekly):,.2f}*\n"
        f"📅 Monthly Bonus: *₹{float(monthly):,.2f}*\n"
        f"{SEP}"
    )


def game_result_text(game: str, won: bool, bet: float, reward: float, tax: float,
                     new_balance: float, emoji: str, currency: str = "INR") -> str:
    sym = "₹" if currency == "INR" else currency
    if won:
        return (
            f"{emoji} *{game.upper()} — YOU WON!*\n"
            f"{SEP}\n"
            f"🎯 Bet: *{sym}{bet:,.4f}*\n"
            f"🏆 Reward: *+{sym}{reward:,.4f}*\n"
            f"🧾 Tax (10%): *-{sym}{tax:,.4f}*\n"
            f"💰 New Balance: *{sym}{new_balance:,.4f}*\n"
            f"{SEP}"
        )
    else:
        return (
            f"{emoji} *{game.upper()} — YOU LOST!*\n"
            f"{SEP}\n"
            f"🎯 Bet: *{sym}{bet:,.4f}*\n"
            f"💸 Lost: *-{sym}{bet:,.4f}*\n"
            f"💰 New Balance: *{sym}{new_balance:,.4f}*\n"
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
        "swap": "🔄", "crypto_deposit": "₿", "crypto_withdraw": "₿"
    }
    for t in txns:
        emoji = type_emoji.get(t['type'], "📌")
        cur = t.get('currency', 'INR')
        sym = "₹" if cur == "INR" else cur
        sign = "+" if t['type'] in ("win", "deposit", "referral", "tip_received", "redeem", "crypto_deposit") else "-"
        lines.append(
            f"{emoji} *{t['type'].upper()}* | {sign}{sym}{t['amount']:,.4f}\n"
            f"   📅 {format_date(t['date'])}"
        )
    return "\n\n".join(lines)


def crypto_deposit_text(symbol: str, network: str, address: str, amount: float) -> str:
    return (
        f"₿ *CRYPTO DEPOSIT*\n"
        f"{SEP}\n"
        f"🪙 Currency: *{symbol}*\n"
        f"🌐 Network: *{network}*\n"
        f"💰 Amount: *{amount:.6f} {symbol}*\n\n"
        f"📋 Send to this address:\n"
        f"`{address}`\n\n"
        f"📌 Steps:\n"
        f"1️⃣ Send *exactly* {amount:.6f} {symbol}\n"
        f"2️⃣ Take screenshot of transaction\n"
        f"3️⃣ Click ✅ Payment Done\n"
        f"{SEP}\n"
        f"⚠️ Send on *{network}* network only!"
    )
