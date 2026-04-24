from utils.helpers import format_date
import html

SEP = "─" * 28


def e(text) -> str:
    """Escape for HTML — prevents ALL Telegram markdown parse errors."""
    return html.escape(str(text))


def main_menu_text(username: str, token_balance: float) -> str:
    return (
        f"🎰 <b>CASINO BOT</b>\n"
        f"{SEP}\n"
        f"👤 Player: <b>{e(username)}</b>\n"
        f"🪙 Tokens: <b>{token_balance:,.4f}</b>\n"
        f"{SEP}\n"
        f"Choose an option below 👇"
    )


def wallet_text(user: dict) -> str:
    return (
        f"💰 <b>WALLET</b>\n"
        f"{SEP}\n"
        f"🪙 Token Balance: <b>{user['token_balance']:,.4f}</b>\n"
        f"📈 Total Wagered: <b>{user['total_wagered']:,.4f}</b> Tokens\n"
        f"🤝 Referral Earnings: <b>{user['referral_earnings']:,.4f}</b> Tokens\n"
        f"{SEP}"
    )


def referral_text(user: dict, ref_count: int, bot_username: str) -> str:
    link = f"https://t.me/{bot_username}?start=ref_{user['user_id']}"
    return (
        f"🤝 <b>REFERRAL PROGRAM</b>\n"
        f"{SEP}\n"
        f"🔗 Your Link:\n<code>{e(link)}</code>\n\n"
        f"👥 Total Referrals: <b>{ref_count}</b>\n"
        f"🪙 Total Earned: <b>{user['referral_earnings']:,.4f}</b> Tokens\n"
        f"{SEP}"
    )


def bonus_text(user: dict, weekly: str, monthly: str, mode: str, tag: str = "", weekly_wager_pct: str = "1", monthly_wager_pct: str = "2") -> str:
    eligible = "✅ Eligible" if user["bonus_eligible"] else "❌ Not Eligible"
    mode_txt = "Fixed Amount" if mode == "fixed" else "Wager-Based %"

    if mode == "wagered":
        weekly_display = f"{weekly_wager_pct}% of your weekly wager"
        monthly_display = f"{monthly_wager_pct}% of your monthly wager"
    else:
        weekly_display = f"{float(weekly):,.0f} Tokens"
        monthly_display = f"{float(monthly):,.0f} Tokens"

    tag_info = ""
    if not user["bonus_eligible"] and tag:
        tag_info = (
            f"\n{SEP}\n"
            f"📌 <b>How to unlock bonus?</b>\n"
            f"Add <b>{tag}</b> to your Telegram\n"
            f"• First name\n"
            f"• Last name\n"
            f"• Username\n\n"
            f"Any one is enough! Then open the bot."
        )
    warn_info = ""
    if user.get("bonus_warned"):
        warn_info = f"\n⚠️ <b>Warning:</b> Tag removed! Restore within 1 hour or progress resets to Day 1."

    return (
        f"🎁 <b>BONUS CENTER</b>\n"
        f"{SEP}\n"
        f"📊 Status: <b>{eligible}</b>\n"
        f"🎰 Mode: <b>{mode_txt}</b>\n\n"
        f"🗓️ Weekly Bonus: <b>{weekly_display}</b>\n"
        f"📅 Monthly Bonus: <b>{monthly_display}</b>\n"
        f"{SEP}"
        f"{warn_info}"
        f"{tag_info}"
    )


def game_result_text(game: str, won: bool, bet: float, reward: float, tax: float, new_balance: float, emoji: str) -> str:
    if won:
        return (
            f"{emoji} <b>{e(game.upper())} — YOU WON!</b>\n"
            f"{SEP}\n"
            f"🎯 Bet: <b>{bet:,.4f}</b> Tokens\n"
            f"🏆 Reward: <b>+{reward:,.4f}</b> Tokens\n"
            f"🧾 Tax (10%): <b>-{tax:,.4f}</b>\n"
            f"🪙 New Balance: <b>{new_balance:,.4f}</b>\n"
            f"{SEP}"
        )
    else:
        return (
            f"{emoji} <b>{e(game.upper())} — YOU LOST!</b>\n"
            f"{SEP}\n"
            f"🎯 Bet: <b>{bet:,.4f}</b> Tokens\n"
            f"💸 Lost: <b>-{bet:,.4f}</b>\n"
            f"🪙 New Balance: <b>{new_balance:,.4f}</b>\n"
            f"{SEP}"
        )


def error_text(msg: str) -> str:
    return f"❌ <b>Error</b>\n{SEP}\n{e(msg)}\n{SEP}"


def success_text(msg: str) -> str:
    return f"✅ <b>Success</b>\n{SEP}\n{msg}\n{SEP}"


def history_text(txns: list) -> str:
    if not txns:
        return f"📋 <b>TRANSACTION HISTORY</b>\n{SEP}\nNo transactions found."
    lines = [f"📋 <b>TRANSACTION HISTORY</b>\n{SEP}"]
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
            f"{emoji} <b>{e(t['type'].upper())}</b> | {sign}{t['amount']:,.4f} 🪙\n"
            f"   📅 {e(format_date(t['date']))}"
        )
    return "\n\n".join(lines)


def leaderboard_text(entries: list, period: str, fake_entries: list = None) -> str:
    """Merge real users (show only first name) with fake entries, sort by wager desc."""
    period_names = {
        "daily": "📅 TODAY'S", "weekly": "📆 THIS WEEK'S",
        "monthly": "🗓️ THIS MONTH'S", "lifetime": "🏆 ALL-TIME"
    }
    title = period_names.get(period, "🏆")
    lines = [f"{title} <b>TOP WAGERS</b>\n{SEP}"]
    medals = ["🥇", "🥈", "🥉"]

    # Build combined list
    combined = []
    for u in (entries or []):
        wager = u.get("wagered") or u.get("total_wagered") or 0
        # Show only first name or anonymized — no username
        fname = u.get("first_name") or ""
        uname = u.get("username") or ""
        display = fname if fname else (uname if uname else f"Player{str(u.get('user_id', '???'))[-4:]}")
        combined.append({"name": display, "wager": wager})
    for f in (fake_entries or []):
        combined.append({"name": f["display_name"], "wager": f["total_wagered"]})

    combined.sort(key=lambda x: x["wager"], reverse=True)

    for i, entry in enumerate(combined[:10]):
        medal = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{medal} {entry['name']} — <b>{entry['wager']:,.0f}</b> 🪙")

    if not combined:
        lines.append("No data yet.")
    lines.append(f"\n{SEP}\n🏅 Top wagerers get exclusive rewards!")
    return "\n".join(lines)
