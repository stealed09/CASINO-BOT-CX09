from aiogram.types import Message, CallbackQuery
from aiogram import Bot
from database import db
from config import ADMIN_IDS
from ui.keyboards import (
    admin_panel_kb, admin_settings_kb, admin_crypto_kb, admin_crypto_detail_kb,
    approve_reject_deposit_kb, approve_reject_withdraw_kb,
    back_kb, admin_wager_kb, admin_user_action_kb
)
from ui.messages import SEP, success_text, error_text, leaderboard_text
from utils.logger import logger


async def show_admin_panel(message: Message):
    users = await db.get_all_users_admin()
    total_tokens = sum(u.get("token_balance", 0) for u in users)
    total_wag = sum(u.get("total_wagered", 0) for u in users)
    await message.answer(
        f"🔐 <b>ADMIN PANEL</b>\n{SEP}\n"
        f"👥 Total Users: <b>{len(users)}</b>\n"
        f"🪙 Total Token Supply: <b>{total_tokens:,.4f}</b>\n"
        f"🎰 Platform Total Wagered: <b>{total_wag:,.4f}</b>\n"
        f"{SEP}",
        parse_mode="HTML", reply_markup=admin_panel_kb()
    )


async def show_pending_deposits(callback: CallbackQuery):
    deposits = await db.get_pending_deposits()
    if not deposits:
        await callback.message.edit_text(
            f"💳 <b>PENDING DEPOSITS</b>\n{SEP}\nNone pending.",
            parse_mode="HTML", reply_markup=back_kb("admin_panel")
        )
        await callback.answer(); return

    await callback.message.edit_text(
        f"💳 <b>PENDING DEPOSITS</b> ({len(deposits)})\n{SEP}",
        parse_mode="HTML", reply_markup=back_kb("admin_panel")
    )

    for dep in deposits:
        method = dep.get("method", "upi").upper()
        if dep.get("method") == "upi":
            amt_line = f"💵 INR: ₹{dep.get('inr_amount', 0):,.2f}"
        elif dep.get("method") == "stars":
            amt_line = f"⭐ Stars: {dep.get('stars_amount', 0)}"
        else:
            amt_line = f"₿ {dep.get('crypto_currency', '')}: {dep.get('crypto_amount', 0):.6f}"

        caption = (
            f"🆔 #{dep['id']} | 👤 <code>{dep['user_id']}</code>\n"
            f"📦 Method: {method}\n"
            f"{amt_line}\n"
            f"🔖 Txn: {dep.get('txn_id') or 'Pending screenshot'}\n"
            f"📅 {dep['date'][:16]}"
        )
        ss_id = dep.get("screenshot_id", "")
        try:
            if ss_id:
                await callback.message.answer_photo(
                    photo=ss_id, caption=caption,
                    parse_mode="HTML", reply_markup=approve_reject_deposit_kb(dep["id"])
                )
            else:
                await callback.message.answer(
                    caption, parse_mode="HTML",
                    reply_markup=approve_reject_deposit_kb(dep["id"])
                )
        except:
            await callback.message.answer(caption, parse_mode="HTML", reply_markup=approve_reject_deposit_kb(dep["id"]))
    await callback.answer()


async def show_pending_withdrawals(callback: CallbackQuery):
    wds = await db.get_pending_withdrawals()
    if not wds:
        await callback.message.edit_text(
            f"💸 <b>PENDING WITHDRAWALS</b>\n{SEP}\nNone pending.",
            parse_mode="HTML", reply_markup=back_kb("admin_panel")
        )
        await callback.answer(); return

    await callback.message.edit_text(
        f"💸 <b>PENDING WITHDRAWALS</b> ({len(wds)})\n{SEP}",
        parse_mode="HTML", reply_markup=back_kb("admin_panel")
    )
    for wd in wds:
        wd_tax = await db.get_effective_withdraw_tax(wd["user_id"])
        tax = round(wd["token_amount"] * wd_tax / 100, 4)
        net = round(wd["token_amount"] - tax, 4)
        method = wd.get("method", "upi")
        if method == "upi":
            dest = f"UPI: <code>{wd.get('upi_id', '')}</code>"
        else:
            dest = f"Crypto: {wd.get('crypto_currency', '')} <code>{wd.get('crypto_address', '')}</code>"
        await callback.message.answer(
            f"🆔 #{wd['id']} | 👤 <code>{wd['user_id']}</code>\n"
            f"🪙 {wd['token_amount']:,.4f} Tokens | Net: {net:,.4f}\n"
            f"📬 {dest}\n"
            f"📅 {wd['date'][:16]}",
            parse_mode="HTML", reply_markup=approve_reject_withdraw_kb(wd["id"])
        )
    await callback.answer()


async def show_admin_stats(callback: CallbackQuery):
    users = await db.get_all_users_admin()
    total_tokens = sum(u.get("token_balance", 0) for u in users)
    total_wag = sum(u.get("total_wagered", 0) for u in users)
    banned = sum(1 for u in users if u.get("is_banned"))
    dep_tax = await db.get_setting("deposit_tax")
    wd_tax = await db.get_setting("withdrawal_tax")
    ref_pct = await db.get_setting("referral_percent")
    inr_rate = await db.get_setting("inr_to_token_rate")
    stars_rate = await db.get_setting("stars_to_token_rate")

    await callback.message.edit_text(
        f"📊 <b>BOT STATS</b>\n{SEP}\n"
        f"👥 Total Users: <b>{len(users)}</b>\n"
        f"🚫 Banned: <b>{banned}</b>\n"
        f"🪙 Total Token Supply: <b>{total_tokens:,.4f}</b>\n"
        f"🎰 Total Wagered: <b>{total_wag:,.4f}</b>\n"
        f"📥 Deposit Tax: <b>{dep_tax}%</b>\n"
        f"📤 Withdraw Tax: <b>{wd_tax}%</b>\n"
        f"🤝 Referral: <b>{ref_pct}%</b>\n"
        f"💱 INR→Token: <b>{inr_rate}</b>\n"
        f"⭐ Stars→Token: <b>{stars_rate}</b>\n"
        f"{SEP}",
        parse_mode="HTML", reply_markup=back_kb("admin_panel")
    )
    await callback.answer()


async def show_admin_settings(callback: CallbackQuery):
    keys = [
        "min_withdrawal_tokens", "withdraw_enabled",
        "weekly_bonus_tokens", "monthly_bonus_tokens", "bonus_mode",
        "upi_id", "deposit_tax", "withdrawal_tax", "referral_percent",
        "inr_to_token_rate", "stars_to_token_rate",
        "crypto_to_token_rate_USDT", "crypto_to_token_rate_BTC", "crypto_to_token_rate_ETH",
        "bonus_wager_percent_weekly", "bonus_wager_percent_monthly",
        "bot_username_tag",
    ]
    vals = {}
    for k in keys:
        vals[k] = await db.get_setting(k) or "?"

    wd_en = "🟢 ON" if vals["withdraw_enabled"] == "1" else "🔴 OFF"

    await callback.message.edit_text(
        f"⚙️ <b>SETTINGS</b>\n{SEP}\n"
        f"💸 Min Withdraw: <b>{vals['min_withdrawal_tokens']} Tokens</b>\n"
        f"🔄 Withdrawals: <b>{wd_en}</b>\n"
        f"🎁 Weekly Bonus: <b>{vals['weekly_bonus_tokens']} T</b>\n"
        f"📅 Monthly Bonus: <b>{vals['monthly_bonus_tokens']} T</b>\n"
        f"🎰 Bonus Mode: <b>{vals['bonus_mode']}</b>\n"
        f"🎯 Wager% Weekly/Monthly: <b>{vals['bonus_wager_percent_weekly']}% / {vals['bonus_wager_percent_monthly']}%</b>\n"
        f"🏷️ Bot Tag: @{vals['bot_username_tag'] or 'not set'}\n"
        f"🏦 UPI: <code>{vals['upi_id']}</code>\n"
        f"📥 Deposit Tax: <b>{vals['deposit_tax']}%</b>\n"
        f"📤 Withdraw Tax: <b>{vals['withdrawal_tax']}%</b>\n"
        f"🤝 Referral: <b>{vals['referral_percent']}%</b>\n"
        f"💱 INR→Token: <b>{vals['inr_to_token_rate']}</b>\n"
        f"⭐ Stars→Token: <b>{vals['stars_to_token_rate']}</b>\n"
        f"₿ USDT→T: <b>{vals['crypto_to_token_rate_USDT']}</b>\n"
        f"₿ BTC→T: <b>{vals['crypto_to_token_rate_BTC']}</b>\n"
        f"₿ ETH→T: <b>{vals['crypto_to_token_rate_ETH']}</b>\n"
        f"{SEP}",
        parse_mode="HTML", reply_markup=admin_settings_kb()
    )
    await callback.answer()


async def show_crypto_manager(callback: CallbackQuery):
    cryptos = await db.get_all_cryptos(enabled_only=False)
    if not cryptos:
        await callback.message.edit_text(
            f"₿ <b>CRYPTO MANAGER</b>\n{SEP}\nNo crypto added yet.",
            parse_mode="HTML", reply_markup=back_kb("admin_panel")
        )
        await callback.answer(); return
    try:
        await callback.message.edit_text(
            f"₿ <b>CRYPTO MANAGER</b>\n{SEP}\nManage deposit currencies:",
            parse_mode="HTML", reply_markup=admin_crypto_kb(cryptos)
        )
    except:
        await callback.message.answer(f"₿ <b>CRYPTO MANAGER</b>", parse_mode="HTML", reply_markup=admin_crypto_kb(cryptos))
    await callback.answer()


async def show_admin_wager(callback: CallbackQuery):
    try:
        await callback.message.edit_text(
            f"🏆 <b>WAGER LEADERBOARD</b>\n{SEP}\nChoose period:",
            parse_mode="HTML", reply_markup=admin_wager_kb()
        )
    except:
        await callback.message.answer("Choose period:", reply_markup=admin_wager_kb())
    await callback.answer()


async def show_wager_by_period(callback: CallbackQuery, period: str):
    entries = await db.get_top_wagers(period, limit=20)
    text = leaderboard_text(entries, period)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_wager_kb())
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=admin_wager_kb())
    await callback.answer()


async def show_user_lookup_prompt(callback: CallbackQuery, state):
    from aiogram.fsm.context import FSMContext
    await callback.answer()
    try:
        await callback.message.edit_text(
            f"👤 <b>USER LOOKUP</b>\n{SEP}\n"
            f"Send user ID or @username to look up:",
            parse_mode="HTML", reply_markup=back_kb("admin_panel")
        )
    except:
        await callback.message.answer("Send user ID or @username:")


async def show_user_full_detail(message: Message, bot: Bot, identifier: str):
    """Look up user by ID or username and show full detail."""
    identifier = identifier.strip()
    if identifier.startswith("@"):
        user = await db.get_user_by_username(identifier[1:])
    elif identifier.isdigit():
        user = await db.get_user_full_detail(int(identifier))
    else:
        user = await db.get_user_by_username(identifier)

    if not user:
        await message.answer(error_text("User not found."), parse_mode="HTML"); return

    uid = user["user_id"]
    user = await db.get_user_full_detail(uid)

    ban_status = "🚫 BANNED" if user.get("is_banned") else "✅ Active"
    dep_tax = user.get("custom_deposit_tax", -1)
    wd_tax = user.get("custom_withdraw_tax", -1)
    dep_tax_str = f"{dep_tax}% (custom)" if dep_tax >= 0 else f"{await db.get_setting('deposit_tax')}% (global)"
    wd_tax_str = f"{wd_tax}% (custom)" if wd_tax >= 0 else f"{await db.get_setting('withdrawal_tax')}% (global)"

    text = (
        f"👤 <b>USER DETAIL</b>\n{SEP}\n"
        f"🆔 ID: <code>{uid}</code>\n"
        f"👤 Username: @{user.get('username', 'N/A')}\n"
        f"📌 Status: {ban_status}\n"
        f"{SEP}\n"
        f"🪙 Token Balance: <b>{user['token_balance']:,.4f}</b>\n"
        f"🎰 Total Wagered: <b>{user['total_wagered']:,.4f}</b>\n"
        f"📅 Daily Wager: <b>{user.get('daily_wagered', 0):,.4f}</b>\n"
        f"📆 Weekly Wager: <b>{user.get('weekly_wagered', 0):,.4f}</b>\n"
        f"🗓️ Monthly Wager: <b>{user.get('monthly_wagered', 0):,.4f}</b>\n"
        f"{SEP}\n"
        f"💳 Deposits: {user.get('dep_count', 0)} | Total: {user.get('total_deposited', 0):,.4f} T\n"
        f"💸 Withdrawals: {user.get('wd_count', 0)} | Total: {user.get('total_withdrawn', 0):,.4f} T\n"
        f"🤝 Referrals: {user.get('referral_count', 0)}\n"
        f"📥 Deposit Tax: {dep_tax_str}\n"
        f"📤 Withdraw Tax: {wd_tax_str}\n"
        f"📅 Joined: {user.get('join_date', 'N/A')[:10]}\n"
        f"{SEP}"
    )
    await message.answer(text, parse_mode="HTML",
                          reply_markup=admin_user_action_kb(uid, bool(user.get("is_banned"))))


async def cmd_add_balance(message: Message, bot: Bot):
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Usage: <code>/addbalance user_id tokens</code>", parse_mode="HTML"); return
    try:
        target, amount = int(parts[1]), float(parts[2])
        user = await db.get_user(target)
        if not user:
            await message.answer(error_text("User not found."), parse_mode="HTML"); return
        await db.update_token_balance(target, amount)
        await db.add_transaction(target, "admin_credit", amount, "admin_credit", currency="TOKEN")
        await message.answer(success_text(f"Added <b>{amount:,.4f}</b> Tokens to <code>{target}</code>"), parse_mode="HTML")
        try:
            await bot.send_message(target, success_text(f"Admin credited <b>{amount:,.4f}</b> Tokens!"), parse_mode="HTML")
        except:
            pass
    except:
        await message.answer(error_text("Invalid input."), parse_mode="HTML")


async def cmd_remove_balance(message: Message, bot: Bot):
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Usage: <code>/removebalance user_id tokens</code>", parse_mode="HTML"); return
    try:
        target, amount = int(parts[1]), float(parts[2])
        user = await db.get_user(target)
        if not user or user["token_balance"] < amount:
            await message.answer(error_text("User not found or insufficient balance."), parse_mode="HTML"); return
        await db.update_token_balance(target, -amount)
        await db.add_transaction(target, "admin_debit", amount, "admin_debit", currency="TOKEN")
        await message.answer(success_text(f"Removed <b>{amount:,.4f}</b> Tokens from <code>{target}</code>"), parse_mode="HTML")
    except:
        await message.answer(error_text("Invalid input."), parse_mode="HTML")


async def cmd_set_balance(message: Message, bot: Bot):
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Usage: <code>/setbalance user_id tokens</code>", parse_mode="HTML"); return
    try:
        target, amount = int(parts[1]), float(parts[2])
        if not await db.get_user(target):
            await message.answer(error_text("User not found."), parse_mode="HTML"); return
        await db.set_token_balance(target, amount)
        await message.answer(success_text(f"Tokens of <code>{target}</code> set to <b>{amount:,.4f}</b>"), parse_mode="HTML")
    except:
        await message.answer(error_text("Invalid input."), parse_mode="HTML")


async def cmd_broadcast(message: Message, bot: Bot):
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        await message.answer("Usage: <code>/broadcast message</code>", parse_mode="HTML"); return
    users = await db.get_all_users()
    sent = failed = 0
    for u in users:
        try:
            await bot.send_message(u["user_id"], f"📢 <b>ANNOUNCEMENT</b>\n{SEP}\n{parts[1]}", parse_mode="HTML")
            sent += 1
        except:
            failed += 1
    await message.answer(success_text(f"Sent: {sent} | Failed: {failed}"), parse_mode="HTML")


async def cmd_tip(message: Message, bot: Bot):
    """Admin tip tokens to user: /tip user_id amount"""
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Usage: <code>/tip user_id tokens</code>", parse_mode="HTML"); return
    try:
        target, amount = int(parts[1]), float(parts[2])
        user = await db.get_user(target)
        if not user:
            await message.answer(error_text("User not found."), parse_mode="HTML"); return
        await db.update_token_balance(target, amount)
        await db.add_transaction(target, "tip_received", amount, "completed", currency="TOKEN")
        await message.answer(success_text(f"Tipped <b>{amount:,.4f}</b> Tokens to <code>{target}</code>"), parse_mode="HTML")
        try:
            await bot.send_message(target, success_text(f"🎁 Admin tipped you <b>{amount:,.4f}</b> Tokens!"), parse_mode="HTML")
        except:
            pass
    except:
        await message.answer(error_text("Invalid input."), parse_mode="HTML")


async def cmd_gencode(message: Message, bot: Bot):
    """Generate redeem code: /gencode amount [code_name]"""
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: <code>/gencode amount [code_name]</code>", parse_mode="HTML"); return
    try:
        amount = float(parts[1])
        import random, string
        code = parts[2].upper() if len(parts) >= 3 else "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        ok = await db.create_redeem_code(code, amount, message.from_user.id)
        if ok:
            await message.answer(
                success_text(f"Code Created!\n🎟️ Code: <code>{code}</code>\n🪙 Tokens: <b>{amount:,.4f}</b>"),
                parse_mode="HTML"
            )
        else:
            await message.answer(error_text("Code already exists or error."), parse_mode="HTML")
    except:
        await message.answer(error_text("Invalid input."), parse_mode="HTML")

async def cmd_regencode(message_or_callback, bot: Bot, code: str = None):
    """Regenerate (deactivate old, generate new) a redeem code."""
    import random, string
    if code:
        # deactivate old
        async with __import__("aiosqlite").connect(db.db_path) as _db:
            async with _db.execute("SELECT * FROM redeem_codes WHERE code=?", (code,)) as cur:
                old = await cur.fetchone()
            if old:
                amount = old[2]
                creator = old[3]
                new_code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
                await _db.execute("UPDATE redeem_codes SET used_by=999999, used_at=datetime('now') WHERE code=?", (code,))
                await _db.execute(
                    "INSERT INTO redeem_codes (code, token_amount, created_by, created_at) VALUES (?, ?, ?, datetime('now'))",
                    (new_code, amount, creator)
                )
                await _db.commit()
                msg = f"♻️ Code Regenerated!\nOld: <code>{code}</code>\nNew: <code>{new_code}</code>\n🪙 Tokens: {amount:,.4f}"
                if hasattr(message_or_callback, 'answer'):
                    await message_or_callback.answer(success_text(msg), parse_mode="HTML")
                else:
                    await message_or_callback.message.answer(success_text(msg), parse_mode="HTML")


async def cmd_tip_group(message, bot: Bot):
    """Tip from group: /tip @username amount (works in groups with tag mention)"""
    parts = message.text.split()
    if len(parts) < 3:
        await message.reply("Usage: <code>/tip @username amount</code>", parse_mode="HTML"); return
    try:
        target_str = parts[1].lstrip("@")
        amount = float(parts[2])
        # Try by username
        user = await db.get_user_by_username(target_str)
        if not user:
            try:
                uid = int(target_str)
                user = await db.get_user(uid)
            except:
                user = None
        if not user:
            await message.reply(error_text(f"User @{target_str} not found."), parse_mode="HTML"); return
        target = user["user_id"]
        await db.update_token_balance(target, amount)
        await db.add_transaction(target, "tip_received", amount, "completed", currency="TOKEN")
        uname = user.get("username") or str(target)
        await message.reply(success_text(f"🎁 Tipped <b>{amount:,.4f}</b> Tokens to @{uname}!"), parse_mode="HTML")
        try:
            await bot.send_message(target, success_text(f"🎁 You received a tip of <b>{amount:,.4f}</b> Tokens!"), parse_mode="HTML")
        except: pass
    except Exception as e:
        await message.reply(error_text(f"Error: {e}"), parse_mode="HTML")
