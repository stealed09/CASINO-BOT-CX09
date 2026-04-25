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


def referral_text(user: dict, ref_count: int, bot_username: str, ref_pct: float = 1.0) -> str:
    link = f"https://t.me/{bot_username}?start=ref_{user['user_id']}"
    return (
        f"🤝 <b>REFERRAL PROGRAM</b>\n"
        f"{SEP}\n"
        f"🔗 Your Link:\n<code>{e(link)}</code>\n\n"
        f"💰 Commission: <b>{ref_pct}%</b> of every bet your referrals place\n\n"
        f"👥 Total Referrals: <b>{ref_count}</b>\n"
        f"🪙 Total Earned: <b>{user['referral_earnings']:,.4f}</b> Tokens\n"
        f"{SEP}"
    )


def bonus_text(user: dict, weekly: str, monthly: str, mode: str, tag: str = "", weekly_wager_pct: str = "1", monthly_wager_pct: str = "2") -> str:
    eligible = "✅ Eligible" if user["bonus_eligible"] else "❌ Not Eligible"
    mode_txt = "Wager-Based %" if mode == "wagered" else "Fixed Amount"

    if mode == "wagered":
        weekly_display = f"{weekly_wager_pct}% of Wagered"
        monthly_display = f"{monthly_wager_pct}% of Wagered"
    else:
        weekly_display = f"{float(weekly):,.0f} Tokens"
        monthly_display = f"{float(monthly):,.0f} Tokens"

    # Warning — shown when tag was removed (1hr grace period active)
    warn_block = ""
    if user.get("bonus_warned"):
        warn_block = (
            f"\n{SEP}\n"
            f"⚠️ <b>WARNING!</b>\n"
            f"You removed the bot tag from your profile!\n"
            f"Restore it within <b>1 hour</b> or your streak resets to <b>Day 1</b>."
        )

    # How to get eligible — shown only when not eligible
    eligible_block = ""
    if not user["bonus_eligible"]:
        tag_display = f"@{tag}" if tag and not tag.startswith("@") else (tag or "bot tag")
        eligible_block = (
            f"\n{SEP}\n"
            f"📌 <b>HOW TO GET ELIGIBLE</b>\n"
            f"Set <b>{tag_display}</b> in your Telegram:\n"
            f"  • First Name\n"
            f"  • Last Name\n"
            f"  • Username\n\n"
            f"Any <b>one</b> of them is enough!\n"
            f"⏳ <b>7 days</b> required for Weekly Bonus\n"
            f"⏳ <b>30 days</b> required for Monthly Bonus"
        )

    return (
        f"🎁 <b>BONUS CENTER</b>\n"
        f"{SEP}\n"
        f"📊 Status: <b>{eligible}</b>\n"
        f"🎰 Mode: <b>{mode_txt}</b>\n"
        f"{SEP}\n"
        f"🗓️ Weekly Bonus:  <b>{weekly_display}</b>\n"
        f"📅 Monthly Bonus: <b>{monthly_display}</b>\n"
        f"{SEP}"
        f"{warn_block}"
        f"{eligible_block}"
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


def leaderboard_text(entries: list, period: str, fake_entries: list = None, min_wager: float = 0) -> str:
    """
    Real users: shown only if wager >= min_wager (admin-set).
      - If wager >= min_wager → show name + token count
      - If below threshold    → excluded entirely
    Fake entries: always shown, name only (no tokens ever).
    """
    period_names = {
        "daily": "📅 TODAY'S", "weekly": "📆 THIS WEEK'S",
        "monthly": "🗓️ THIS MONTH'S", "lifetime": "🏆 ALL-TIME"
    }
    title = period_names.get(period, "🏆")
    lines = [f"{title} <b>TOP WAGERS</b>\n{SEP}"]
    medals = ["🥇", "🥈", "🥉"]

    combined = []

    # Real users — filter by threshold AND exclude 0 wager
    for u in (entries or []):
        wager = u.get("wagered") or u.get("total_wagered") or 0
        if wager <= 0:
            continue  # Never show 0 wager users
        if min_wager > 0 and wager < min_wager:
            continue  # Below admin threshold — hide
        fname = (u.get("first_name") or "").strip()
        display = fname if fname else f"Player{str(u.get('user_id', '???'))[-4:]}"
        combined.append({"name": display, "wager": wager, "real": True})

    # Fake entries — always included, name only
    for f in (fake_entries or []):
        name = (f.get("display_name") or "Player").lstrip("@")
        combined.append({"name": name, "wager": f["total_wagered"], "real": False})

    combined.sort(key=lambda x: x["wager"], reverse=True)

    for i, entry in enumerate(combined[:10]):
        medal = medals[i] if i < 3 else f"{i+1}."
        if entry["real"]:
            lines.append(f"{medal} {entry['name']} — <b>{entry['wager']:,.0f} 🪙</b>")
        else:
            lines.append(f"{medal} {entry['name']} — <b>{entry['wager']:,.0f} 🪙</b>")

    if not combined:
        lines.append("No data yet.")
    lines.append(f"\n{SEP}\n🏅 Top wagerers get exclusive rewards!")
    return "\n".join(lines)
