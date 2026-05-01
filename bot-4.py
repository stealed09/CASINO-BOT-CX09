"""
P2P Telegram Escrow Bot
No aiohttp — uses urllib only | Admin sets all credentials via bot panel
"""

import asyncio
import uuid
import io
import json
import logging
import urllib.request
import urllib.parse
import qrcode
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from telethon import TelegramClient
from telethon.tl.functions.channels import (
    CreateChannelRequest, InviteToChannelRequest,
    EditAdminRequest, ExportInviteRequest
)
from telethon.tl.types import ChatAdminRights
from config import BOT_TOKEN, MAIN_ADMIN_ID, state

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════
# HTTP HELPER (no aiohttp)
# ══════════════════════════════════════════════════════════

def http_post(url, payload: dict) -> dict:
    """Synchronous HTTP POST using stdlib urllib."""
    data = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))

async def async_post(url, payload: dict) -> dict:
    """Run blocking http_post in thread so it doesn't block the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, http_post, url, payload)

# ══════════════════════════════════════════════════════════
# TELETHON — start & group creation
# ══════════════════════════════════════════════════════════

async def start_telethon():
    """Start Telethon client using credentials stored in state."""
    if not state.api_id or not state.api_hash or not state.phone:
        logger.warning("Telethon credentials not set. Auto group creation disabled.")
        return
    try:
        client = TelegramClient("escrow_session", int(state.api_id), state.api_hash)
        await client.start(phone=state.phone)
        state.telethon_client = client
        logger.info("✅ Telethon client started.")
    except Exception as e:
        logger.error(f"Telethon start failed: {e}")

async def create_group_telethon(title: str, bot_username: str):
    client = state.telethon_client
    if not client:
        return None, None
    try:
        result = await client(CreateChannelRequest(title=title, about="P2P Escrow Deal", megagroup=True))
        channel = result.chats[0]
        group_id = int(f"-100{channel.id}")
        bot_entity = await client.get_entity(bot_username)
        await client(InviteToChannelRequest(channel=channel, users=[bot_entity]))
        rights = ChatAdminRights(
            post_messages=True, edit_messages=True, delete_messages=True,
            ban_users=True, invite_users=True, pin_messages=True,
            add_admins=False, manage_call=True, other=True
        )
        await client(EditAdminRequest(channel=channel, user_id=bot_entity, admin_rights=rights, rank="Escrow Bot"))
        invite = await client(ExportInviteRequest(peer=channel))
        return group_id, invite.link
    except Exception as e:
        logger.error(f"Telethon group creation failed: {e}")
        return None, None

async def delete_group_telethon(group_id):
    from telethon.tl.functions.channels import DeleteChannelRequest
    if not state.telethon_client:
        return
    try:
        entity = await state.telethon_client.get_entity(group_id)
        await state.telethon_client(DeleteChannelRequest(entity))
    except Exception as e:
        logger.warning(f"Group delete failed: {e}")

# ══════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════

def is_main_admin(uid): return uid == MAIN_ADMIN_ID
def is_admin(uid):      return uid == MAIN_ADMIN_ID or uid in state.sub_admins
def trade_id():         return "TRD-" + str(uuid.uuid4()).upper()[:8]

def deal_by_group(cid):
    did = state.group_to_deal.get(cid)
    return (did, state.deals.get(did)) if did else (None, None)

def deal_by_id(did): return state.deals.get(did)

def new_deal(tid, group_id, creator_id):
    return {
        "trade_id": tid, "group_id": group_id, "status": "SETUP",
        "creator_id": creator_id,
        "buyer_id": None, "buyer_username": None, "buyer_address": None,
        "seller_id": None, "seller_username": None, "seller_address": None,
        "quantity": None, "rate": None, "condition": None, "token": None,
        "token_buyer_confirmed": False, "token_seller_confirmed": False,
        "deposit_address": None,
        "buyer_confirmed": False, "seller_confirmed": False,
        "funded": False, "created_at": datetime.utcnow().isoformat()
    }

async def log(ctx, msg):
    if state.log_group_id:
        try:
            await ctx.bot.send_message(chat_id=state.log_group_id, text=f"📋 LOG\n\n{msg}", parse_mode="HTML")
        except Exception as e:
            logger.error(f"Log error: {e}")

async def alert_admins(ctx, msg, deal_id=None):
    for uid in [MAIN_ADMIN_ID] + list(state.sub_admins):
        try:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚨 Handle Dispute", callback_data=f"dispute_handle:{deal_id}")]]) if deal_id else None
            await ctx.bot.send_message(chat_id=uid, text=msg, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass

def make_qr_bytes(data):
    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()

async def send_qr(ctx, chat_id, address, caption):
    try:
        await ctx.bot.send_photo(
            chat_id=chat_id,
            photo=InputFile(io.BytesIO(make_qr_bytes(address)), filename="qr.png"),
            caption=caption, parse_mode="HTML"
        )
    except Exception:
        await ctx.bot.send_message(chat_id=chat_id, text=caption, parse_mode="HTML")

# ══════════════════════════════════════════════════════════
# /start
# ══════════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🤝 Start Deal", callback_data="start_deal")],
        [InlineKeyboardButton("📖 Instructions", callback_data="show_instructions")]
    ])
    await update.message.reply_text(
        "👋 <b>Welcome to P2P Escrow Bot</b>\n\nSecure peer-to-peer trading.\n\nChoose an option:",
        reply_markup=kb, parse_mode="HTML"
    )

# ══════════════════════════════════════════════════════════
# /instructions
# ══════════════════════════════════════════════════════════

async def cmd_instructions(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 <b>HOW TO USE ESCROW BOT</b>\n\n"
        "<b>1️⃣</b> /start → <b>Start Deal</b> → bot creates private group\n\n"
        "<b>2️⃣</b> Both join → <b>/dd</b> [qty] [rate] [condition]\n\n"
        "<b>3️⃣</b> <b>/buyer</b> [address]  and  <b>/seller</b> [address]\n\n"
        "<b>4️⃣</b> <b>/token</b> → select → both confirm\n\n"
        "<b>5️⃣</b> <b>/deposit</b> → get escrow address + QR code\n\n"
        "<b>6️⃣</b> <b>/verify</b> → mark funded → buyer pays seller privately\n\n"
        "<b>7️⃣</b> Both press <b>Confirm</b> → deal auto-releases\n\n"
        "<b>8️⃣</b> <b>/dispute</b> → call admin if any issue\n\n"
        "⚠️ <i>All steps must be done inside your deal group</i>"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="HTML")
    else:
        await update.message.reply_text(text, parse_mode="HTML")

# ══════════════════════════════════════════════════════════
# ADMIN PANEL — all credentials set here
# ══════════════════════════════════════════════════════════

def admin_panel_kb():
    tc = "✅ ON" if state.telethon_client else "❌ OFF"
    ox = "✅ SET" if state.oxapay_key else "❌ NOT SET"
    lg = "✅ SET" if state.log_group_id else "❌ NOT SET"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📋 Log Group {lg}", callback_data="adm:setloggroup"),
         InlineKeyboardButton("📊 Status", callback_data="adm:status")],
        [InlineKeyboardButton("➕ Add Admin", callback_data="adm:addadmin"),
         InlineKeyboardButton("➖ Remove Admin", callback_data="adm:removeadmin")],
        [InlineKeyboardButton("💸 Set Fee", callback_data="adm:setfee"),
         InlineKeyboardButton("🏷 Set Bio Tag", callback_data="adm:setbio")],
        [InlineKeyboardButton(f"🔑 OxaPay {ox}", callback_data="adm:setoxapay"),
         InlineKeyboardButton("✅ Check OxaPay", callback_data="adm:checkoxapay")],
        [InlineKeyboardButton("🗑 Reset OxaPay", callback_data="adm:resetoxapay"),
         InlineKeyboardButton(f"📡 Telethon {tc}", callback_data="adm:telethon")],
        [InlineKeyboardButton("👥 List Admins", callback_data="adm:listadmins"),
         InlineKeyboardButton("🔄 Refresh", callback_data="adm:refresh")]
    ])

async def cmd_adminpanel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_main_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "👑 <b>ADMIN CONTROL PANEL</b>\n\nAll settings managed here:",
        reply_markup=admin_panel_kb(), parse_mode="HTML"
    )

# ══════════════════════════════════════════════════════════
# CALLBACK ROUTER
# ══════════════════════════════════════════════════════════

async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    if d == "start_deal":                  await handle_start_deal(update, ctx)
    elif d == "show_instructions":         await cmd_instructions(update, ctx)
    elif d.startswith("token_select:"):    await handle_token_pick(update, ctx, d)
    elif d.startswith("token_confirm:"):   await handle_token_confirm(update, ctx, d)
    elif d.startswith("token_reselect:"): await handle_token_reselect(update, ctx, d)
    elif d.startswith("confirm:"):         await handle_confirmation(update, ctx, d)
    elif d.startswith("dispute_handle:"): await handle_dispute_admin(update, ctx, d)
    elif d == "dispute_call":              await handle_dispute_call(update, ctx)
    elif d.startswith("adm:"):             await handle_admin_cb(update, ctx, d)

# ══════════════════════════════════════════════════════════
# ADMIN PANEL CALLBACKS
# ══════════════════════════════════════════════════════════

async def handle_admin_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE, d: str):
    q = update.callback_query
    if not is_main_admin(q.from_user.id):
        await q.answer("❌ Access denied.", show_alert=True)
        return

    action = d.split(":")[1]

    # ── STATUS ──
    if action in ("status", "refresh"):
        all_d = list(state.deals.values())
        total = len(all_d)
        done  = sum(1 for x in all_d if x["status"] == "COMPLETED")
        dis   = sum(1 for x in all_d if x["status"] == "DISPUTED")
        fund  = sum(1 for x in all_d if x["status"] == "FUNDED")
        ox = f"✅ {state.oxapay_key[:4]}...{state.oxapay_key[-4:]}" if state.oxapay_key else "❌ Not Set (Demo)"
        lg = f"✅ <code>{state.log_group_id}</code>" if state.log_group_id else "❌ Not Set"
        tc = "✅ Connected" if state.telethon_client else "❌ Not Connected"
        await q.edit_message_text(
            f"📊 <b>BOT STATUS</b>\n\n"
            f"📋 Log Group: {lg}\n🔑 OxaPay: {ox}\n📡 Telethon: {tc}\n"
            f"💸 Fee: <b>{state.fee_percent}%</b>\n🏷 Bio Tag: <b>{state.required_bio or 'Not Set'}</b>\n"
            f"👥 Sub Admins: <b>{len(state.sub_admins)}</b>\n\n"
            f"📦 Total: {total}  🟢 Active: {total-done}  ✅ Done: {done}\n"
            f"💰 Funded: {fund}  🚨 Disputed: {dis}\n\n"
            f"🤖 Mode: {'LIVE' if state.oxapay_key else 'DEMO'}",
            parse_mode="HTML", reply_markup=admin_panel_kb()
        )

    # ── LIST ADMINS ──
    elif action == "listadmins":
        txt = f"👑 Main: <code>{MAIN_ADMIN_ID}</code>\n\n"
        txt += ("👨‍💼 Sub Admins:\n" + "".join(f"{i}. <code>{a}</code>\n" for i, a in enumerate(state.sub_admins, 1))) if state.sub_admins else "👨‍💼 Sub Admins: None"
        await q.edit_message_text(f"📋 <b>ADMIN LIST</b>\n\n{txt}", parse_mode="HTML", reply_markup=admin_panel_kb())

    # ── CHECK OXAPAY ──
    elif action == "checkoxapay":
        if not state.oxapay_key:
            await q.edit_message_text("❌ OxaPay key not set.\n\nUse /setoxapay to set it.", parse_mode="HTML", reply_markup=admin_panel_kb())
            return
        await q.edit_message_text("⏳ Checking OxaPay connection…", parse_mode="HTML")
        try:
            data = await async_post("https://api.oxapay.com/merchants/balance", {"merchant": state.oxapay_key})
            if data.get("result") == 100:
                bal = data.get("balance", {})
                bal_txt = "\n".join(f"  • {k}: {v}" for k, v in bal.items()) if bal else "N/A"
                txt = f"✅ <b>OxaPay Connected!</b>\n\n💰 Balances:\n{bal_txt}"
            else:
                txt = f"⚠️ OxaPay Error: {data.get('message', 'Unknown')}"
        except Exception as e:
            txt = f"❌ Connection failed: {e}"
        await q.edit_message_text(txt, parse_mode="HTML", reply_markup=admin_panel_kb())

    # ── RESET OXAPAY ──
    elif action == "resetoxapay":
        state.oxapay_key = None
        await q.edit_message_text("✅ OxaPay key removed. Bot in DEMO mode.", parse_mode="HTML", reply_markup=admin_panel_kb())

    # ── SET LOG GROUP ──
    elif action == "setloggroup":
        await q.edit_message_text(
            "📋 <b>Set Log Group</b>\n\n"
            "1. Create a private Telegram group\n"
            "2. Add this bot as <b>Admin</b>\n"
            "3. Send <code>/setloggroup</code> <b>inside that group</b>\n\n"
            "⬅️ /adminpanel to go back",
            parse_mode="HTML"
        )

    # ── TELETHON SETUP ──
    elif action == "telethon":
        tc = "✅ Connected" if state.telethon_client else "❌ Not Connected"
        await q.edit_message_text(
            f"📡 <b>TELETHON SETUP</b>\n\nStatus: {tc}\n\n"
            f"Telethon allows the bot to auto-create groups.\n\n"
            f"<b>Set credentials with these commands:</b>\n"
            f"<code>/setapiid YOUR_API_ID</code>\n"
            f"<code>/setapihash YOUR_API_HASH</code>\n"
            f"<code>/setphone +1234567890</code>\n"
            f"<code>/starttelethon</code> — connect\n\n"
            f"Get API ID & Hash from: https://my.telegram.org\n\n"
            f"Current:\n"
            f"• API ID: <b>{'✅ Set' if state.api_id else '❌ Not Set'}</b>\n"
            f"• API Hash: <b>{'✅ Set' if state.api_hash else '❌ Not Set'}</b>\n"
            f"• Phone: <b>{'✅ Set' if state.phone else '❌ Not Set'}</b>\n\n"
            f"⬅️ /adminpanel",
            parse_mode="HTML"
        )

    # ── PROMPT COMMANDS ──
    elif action in ("addadmin", "removeadmin", "setfee", "setbio", "setoxapay"):
        prompts = {
            "addadmin":    ("➕ <b>Add Sub Admin</b>",   "/addadmin {user_id}"),
            "removeadmin": ("➖ <b>Remove Sub Admin</b>","/removeadmin {user_id}"),
            "setfee":      ("💸 <b>Set Fee %</b>",       f"/setfee {{percent}}  ← current: {state.fee_percent}%"),
            "setbio":      ("🏷 <b>Set Bio Tag</b>",     f"/setbio {{tag}}  ← current: {state.required_bio or 'Not set'}"),
            "setoxapay":   ("🔑 <b>Set OxaPay Key</b>", "/setoxapay {api_key}"),
        }
        title, usage = prompts[action]
        await q.edit_message_text(f"{title}\n\nSend the command:\n<code>{usage}</code>\n\n⬅️ /adminpanel", parse_mode="HTML")

# ══════════════════════════════════════════════════════════
# STEP 2: START DEAL
# ══════════════════════════════════════════════════════════

async def handle_start_deal(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user = q.from_user

    if not state.log_group_id:
        await q.edit_message_text(
            "❌ <b>Cannot create deal.</b>\n\nAdmin has not set the LOG GROUP yet.\nContact the administrator.",
            parse_mode="HTML"
        )
        return

    await q.edit_message_text("⏳ <b>Creating your private deal group…</b>\nPlease wait a moment.", parse_mode="HTML")

    tid = trade_id()
    group_id, invite_url = None, None

    if state.telethon_client:
        bot_me = await ctx.bot.get_me()
        group_id, invite_url = await create_group_telethon(f"🔒 Escrow {tid}", bot_me.username)

    if not group_id:
        await ctx.bot.send_message(
            chat_id=user.id,
            text=(
                "⚠️ <b>Auto Group Creation Not Available</b>\n\n"
                "Telethon is not connected yet.\n\n"
                "Please do this manually:\n"
                "1️⃣ Create a Telegram group\n"
                "2️⃣ Add this bot as <b>Admin</b>\n"
                "3️⃣ Run <code>/initdeal</code> inside the group\n\n"
                "Or ask the admin to set up Telethon via /adminpanel → 📡 Telethon"
            ),
            parse_mode="HTML"
        )
        return

    deal = new_deal(tid, group_id, user.id)
    state.deals[tid] = deal
    state.group_to_deal[group_id] = tid

    await ctx.bot.send_message(
        chat_id=user.id,
        text=(
            f"✅ <b>Deal Group Created!</b>\n\n"
            f"🆔 Trade ID: <code>{tid}</code>\n"
            f"🔗 Invite Link:\n{invite_url}\n\n"
            f"Share this link with the other party.\n\n"
            f"➡️ <b>Next step:</b> Both join the group → use <b>/dd</b>"
        ),
        parse_mode="HTML"
    )

    try:
        await ctx.bot.send_message(
            chat_id=group_id,
            text=(
                f"🔒 <b>Escrow Deal Group Ready</b>\n\n"
                f"🆔 Trade ID: <code>{tid}</code>\n\n"
                f"Both buyer and seller must join this group.\n\n"
                f"➡️ <b>Next step:</b> Use <b>/dd</b> to fill deal details."
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Welcome msg failed: {e}")

    await log(ctx,
        f"🆕 <b>DEAL CREATED</b>\n\n🆔 <code>{tid}</code>\n"
        f"👤 @{user.username} ({user.id})\n📦 <code>{group_id}</code>\n"
        f"🔗 {invite_url}\n⏰ {deal['created_at']}"
    )

# ══════════════════════════════════════════════════════════
# /initdeal — manual fallback
# ══════════════════════════════════════════════════════════

async def cmd_initdeal(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if chat.type == "private":
        await update.message.reply_text("❌ Use inside a group.")
        return
    if not state.log_group_id:
        await update.message.reply_text("❌ <b>LOG GROUP not set.</b> Admin must run /setloggroup first.", parse_mode="HTML")
        return
    if chat.id in state.group_to_deal:
        await update.message.reply_text("⚠️ This group already has an active deal.")
        return
    tid  = trade_id()
    deal = new_deal(tid, chat.id, user.id)
    state.deals[tid] = deal
    state.group_to_deal[chat.id] = tid
    await update.message.reply_text(
        f"🔒 <b>Deal Initialized</b>\n\n🆔 <code>{tid}</code>\n\n➡️ <b>Next step:</b> Use <b>/dd</b>",
        parse_mode="HTML"
    )
    await log(ctx, f"🆕 <b>DEAL CREATED</b>\n\n🆔 <code>{tid}</code>\n👤 @{user.username}\n📦 <code>{chat.id}</code>\n⏰ {deal['created_at']}")

# ══════════════════════════════════════════════════════════
# STEP 3: /dd
# ══════════════════════════════════════════════════════════

async def cmd_dd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("❌ Use inside your deal group.")
        return
    did, deal = deal_by_group(chat.id)
    if not deal:
        await update.message.reply_text("❌ No active deal. Use /initdeal first.")
        return
    if deal["status"] != "SETUP":
        await update.message.reply_text(f"⚠️ Deal in <b>{deal['status']}</b> — cannot edit form.", parse_mode="HTML")
        return
    if not ctx.args or len(ctx.args) < 2:
        await update.message.reply_text(
            "📋 <b>DEAL FORM</b>\n\nFormat:\n<code>/dd [quantity] [rate] [condition]</code>\n\nExample:\n<code>/dd 500 1.02 Payment within 30 minutes</code>",
            parse_mode="HTML"
        )
        return
    deal["quantity"]  = ctx.args[0]
    deal["rate"]      = ctx.args[1]
    deal["condition"] = " ".join(ctx.args[2:]) if len(ctx.args) > 2 else "None"
    await update.message.reply_text(
        f"✅ <b>Deal Form Saved!</b>\n\n"
        f"💰 Quantity: {deal['quantity']}\n📈 Rate: {deal['rate']}\n📝 Condition: {deal['condition']}\n\n"
        f"➡️ <b>Next step:</b>\n<code>/buyer [wallet_address]</code>\n<code>/seller [wallet_address]</code>",
        parse_mode="HTML"
    )

# ══════════════════════════════════════════════════════════
# STEP 4: /buyer & /seller
# ══════════════════════════════════════════════════════════

async def cmd_buyer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await set_role(update, ctx, "buyer")

async def cmd_seller(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await set_role(update, ctx, "seller")

async def set_role(update: Update, ctx: ContextTypes.DEFAULT_TYPE, role: str):
    chat = update.effective_chat
    user = update.effective_user
    if chat.type == "private":
        await update.message.reply_text("❌ Use inside your deal group.")
        return
    did, deal = deal_by_group(chat.id)
    if not deal:
        await update.message.reply_text("❌ No active deal here.")
        return
    if deal["status"] != "SETUP":
        await update.message.reply_text(f"⚠️ Cannot change roles. Status: <b>{deal['status']}</b>", parse_mode="HTML")
        return
    if not ctx.args:
        await update.message.reply_text(f"❌ Provide wallet address.\nExample: <code>/{role} YourAddress</code>", parse_mode="HTML")
        return
    deal[f"{role}_id"]       = user.id
    deal[f"{role}_username"] = user.username or user.first_name
    deal[f"{role}_address"]  = ctx.args[0]
    label = "🛒 Buyer" if role == "buyer" else "🏪 Seller"
    b = deal.get("buyer_id") is not None
    s = deal.get("seller_id") is not None
    if b and s:
        deal["status"] = "ROLES_SET"
        nxt = "✅ Both roles set!\n\n➡️ <b>Next step:</b> Use <b>/token</b>"
    elif b:
        nxt = "⏳ Waiting for seller: <code>/seller [address]</code>"
    else:
        nxt = "⏳ Waiting for buyer: <code>/buyer [address]</code>"
    await update.message.reply_text(
        f"✅ <b>{label} Set!</b>\n\n👤 @{deal[f'{role}_username']}\n💳 <code>{ctx.args[0]}</code>\n\n{nxt}",
        parse_mode="HTML"
    )

# ══════════════════════════════════════════════════════════
# STEP 5: /token
# ══════════════════════════════════════════════════════════

TOKEN_LABELS = {
    "USDT_TRC20": "💵 USDT TRC20", "USDT_BEP20": "💵 USDT BEP20",
    "BTC": "₿ BTC", "LTC": "Ł LTC"
}

def token_select_kb(did):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💵 USDT TRC20", callback_data=f"token_select:USDT_TRC20:{did}"),
         InlineKeyboardButton("💵 USDT BEP20", callback_data=f"token_select:USDT_BEP20:{did}")],
        [InlineKeyboardButton("₿ BTC", callback_data=f"token_select:BTC:{did}"),
         InlineKeyboardButton("Ł LTC", callback_data=f"token_select:LTC:{did}")]
    ])

async def cmd_token(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("❌ Use inside your deal group.")
        return
    did, deal = deal_by_group(chat.id)
    if not deal:
        await update.message.reply_text("❌ No active deal here.")
        return
    if deal.get("funded"):
        await update.message.reply_text("❌ Token locked — payment already made.")
        return
    if deal["status"] not in ("ROLES_SET", "TOKEN_SELECTED"):
        await update.message.reply_text(f"⚠️ Complete previous steps first. Status: <b>{deal['status']}</b>", parse_mode="HTML")
        return
    await update.message.reply_text(
        "🪙 <b>SELECT PAYMENT TOKEN</b>\n\n⚠️ <i>Both buyer AND seller must confirm.</i>",
        reply_markup=token_select_kb(did), parse_mode="HTML"
    )

async def handle_token_pick(update: Update, ctx: ContextTypes.DEFAULT_TYPE, d: str):
    q = update.callback_query
    user = q.from_user
    _, token, did = d.split(":")
    deal = deal_by_id(did)
    if not deal:
        await q.edit_message_text("❌ Deal not found.")
        return
    if user.id not in (deal.get("buyer_id"), deal.get("seller_id")):
        await q.answer("❌ Only deal participants can select token.", show_alert=True)
        return
    if deal.get("funded"):
        await q.answer("❌ Token locked after payment.", show_alert=True)
        return
    deal["token"] = token
    deal["token_buyer_confirmed"]  = False
    deal["token_seller_confirmed"] = False
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Confirm Token", callback_data=f"token_confirm:{did}"),
        InlineKeyboardButton("🔄 Re-select", callback_data=f"token_reselect:{did}")
    ]])
    await q.edit_message_text(
        f"🪙 <b>Token Proposed: {TOKEN_LABELS.get(token, token)}</b>\n\n"
        f"Selected by: @{user.username or user.first_name}\n\n"
        f"⚠️ <b>BOTH buyer and seller must confirm.</b>",
        reply_markup=kb, parse_mode="HTML"
    )

async def handle_token_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE, d: str):
    q = update.callback_query
    user = q.from_user
    _, did = d.split(":", 1)
    deal = deal_by_id(did)
    if not deal:
        await q.answer("❌ Deal not found.", show_alert=True)
        return
    if user.id == deal.get("buyer_id"):    role = "buyer"
    elif user.id == deal.get("seller_id"): role = "seller"
    else:
        await q.answer("❌ Not a deal participant.", show_alert=True)
        return
    deal[f"token_{role}_confirmed"] = True
    await q.answer(f"✅ {role.capitalize()} confirmed!")
    b_ok = deal.get("token_buyer_confirmed")
    s_ok = deal.get("token_seller_confirmed")
    label = TOKEN_LABELS.get(deal["token"], deal["token"])
    if b_ok and s_ok:
        deal["status"] = "TOKEN_SELECTED"
        await q.edit_message_text(
            f"🔒 <b>Token Locked: {label}</b>\n\n✅ Buyer: Confirmed\n✅ Seller: Confirmed\n\n"
            f"➡️ <b>Next step:</b> Seller uses <b>/deposit</b>",
            parse_mode="HTML"
        )
    else:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Confirm Token", callback_data=f"token_confirm:{did}"),
            InlineKeyboardButton("🔄 Re-select", callback_data=f"token_reselect:{did}")
        ]])
        await q.edit_message_text(
            f"🪙 <b>Token: {label}</b>\n\n"
            f"🛒 Buyer: {'✅ Confirmed' if b_ok else '⏳ Waiting'}\n"
            f"🏪 Seller: {'✅ Confirmed' if s_ok else '⏳ Waiting'}\n\n"
            f"⚠️ Both must confirm before proceeding.",
            reply_markup=kb, parse_mode="HTML"
        )

async def handle_token_reselect(update: Update, ctx: ContextTypes.DEFAULT_TYPE, d: str):
    q = update.callback_query
    user = q.from_user
    _, did = d.split(":", 1)
    deal = deal_by_id(did)
    if not deal:
        await q.answer("❌ Deal not found.", show_alert=True)
        return
    if user.id not in (deal.get("buyer_id"), deal.get("seller_id")):
        await q.answer("❌ Not a deal participant.", show_alert=True)
        return
    deal["token"] = None
    deal["token_buyer_confirmed"]  = False
    deal["token_seller_confirmed"] = False
    await q.edit_message_text("🪙 <b>Re-select Token:</b>", reply_markup=token_select_kb(did), parse_mode="HTML")

# ══════════════════════════════════════════════════════════
# STEP 6: /deposit
# ══════════════════════════════════════════════════════════

async def cmd_deposit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("❌ Use inside your deal group.")
        return
    did, deal = deal_by_group(chat.id)
    if not deal:
        await update.message.reply_text("❌ No active deal here.")
        return
    if deal["status"] not in ("TOKEN_SELECTED", "AWAITING_DEPOSIT"):
        await update.message.reply_text("❌ Select and confirm token first using <b>/token</b>", parse_mode="HTML")
        return

    if not state.oxapay_key:
        demo_addr = f"DEMO_{did[:8]}"
        deal["deposit_address"] = demo_addr
        deal["status"] = "AWAITING_DEPOSIT"
        await send_qr(ctx, chat.id, demo_addr,
            f"🔧 <b>DEMO DEPOSIT ADDRESS</b>\n\n🪙 Token: {deal.get('token')}\n"
            f"📬 Address:\n<code>{demo_addr}</code>\n💰 Amount: {deal.get('quantity')}\n\n"
            f"⚠️ DEMO mode — no real payment needed.\n\n➡️ <b>Next step:</b> Use <b>/verify</b>"
        )
        return

    await update.message.reply_text("⏳ Generating deposit address via OxaPay…")
    token_map = {
        "USDT_TRC20": ("USDT","TRX"), "USDT_BEP20": ("USDT","BSC"),
        "BTC": ("BTC","BTC"), "LTC": ("LTC","LTC")
    }
    currency, network = token_map.get(deal["token"], ("USDT","TRX"))
    try:
        data = await async_post("https://api.oxapay.com/merchants/request", {
            "merchant": state.oxapay_key, "amount": float(deal.get("quantity", 1)),
            "currency": currency, "network": network,
            "description": f"Escrow {did}", "lifeTime": 60
        })
        if data.get("result") != 100:
            raise Exception(data.get("message", "Unknown error"))
        address = data.get("payAddress", "N/A")
        deal["deposit_address"] = address
        deal["status"] = "AWAITING_DEPOSIT"
        await send_qr(ctx, chat.id, address,
            f"✅ <b>DEPOSIT ADDRESS READY</b>\n\n🪙 Token: {deal['token']}\n"
            f"📬 Address:\n<code>{address}</code>\n💰 Amount: {deal.get('quantity')}\n\n"
            f"⚠️ Send EXACT amount.\n\n➡️ <b>Next step:</b> Use <b>/verify</b> after sending."
        )
    except Exception as e:
        fallback = f"DEMO_{did[:8]}"
        deal["deposit_address"] = fallback
        deal["status"] = "AWAITING_DEPOSIT"
        await update.message.reply_text(
            f"❌ OxaPay Error: {e}\n\n🔧 Demo fallback: <code>{fallback}</code>\n\n➡️ Use <b>/verify</b>",
            parse_mode="HTML"
        )

# ══════════════════════════════════════════════════════════
# STEP 7: /verify
# ══════════════════════════════════════════════════════════

async def cmd_verify(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if chat.type == "private":
        await update.message.reply_text("❌ Use inside your deal group.")
        return
    did, deal = deal_by_group(chat.id)
    if not deal:
        await update.message.reply_text("❌ No active deal here.")
        return
    if deal.get("funded"):
        await update.message.reply_text("⚠️ Deal already FUNDED.")
        return
    if deal["status"] != "AWAITING_DEPOSIT":
        await update.message.reply_text("❌ Use /deposit first.")
        return
    deal["funded"]    = True
    deal["status"]    = "FUNDED"
    deal["funded_by"] = user.username or user.first_name
    deal["funded_at"] = datetime.utcnow().isoformat()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Buyer Confirm", callback_data=f"confirm:buyer:{did}"),
         InlineKeyboardButton("✅ Seller Confirm", callback_data=f"confirm:seller:{did}")],
        [InlineKeyboardButton("🚨 Dispute / Call Admin", callback_data="dispute_call")]
    ])
    await update.message.reply_text(
        f"✅ <b>PAYMENT FUNDED!</b>\n\n🆔 <code>{did}</code>\n🪙 {deal.get('token')}\n💰 {deal.get('quantity')}\n\n"
        f"────────────────────\n"
        f"<b>BUYER:</b> Now send payment to seller privately.\n"
        f"Once seller confirms receipt, BOTH press Confirm below.\n\n"
        f"⚠️ Deal releases ONLY when BOTH confirm.",
        reply_markup=kb, parse_mode="HTML"
    )
    await log(ctx, f"💰 <b>DEAL FUNDED</b>\n\n🆔 <code>{did}</code>\n🪙 {deal.get('token')}\n💵 {deal.get('quantity')}\n👤 @{deal['funded_by']}\n⏰ {deal['funded_at']}")

# ══════════════════════════════════════════════════════════
# STEP 8: CONFIRMATION
# ══════════════════════════════════════════════════════════

async def handle_confirmation(update: Update, ctx: ContextTypes.DEFAULT_TYPE, d: str):
    q = update.callback_query
    user = q.from_user
    _, role, did = d.split(":")
    deal = deal_by_id(did)
    if not deal:
        await q.answer("❌ Deal not found.", show_alert=True)
        return
    if not deal.get("funded"):
        await q.answer("❌ Deal not funded yet.", show_alert=True)
        return
    if deal.get("status") == "COMPLETED":
        await q.answer("✅ Already completed.", show_alert=True)
        return
    if role == "buyer":
        if user.id != deal.get("buyer_id"):
            await q.answer("❌ You are not the buyer.", show_alert=True)
            return
        if deal.get("buyer_confirmed"):
            await q.answer("✅ Already confirmed.", show_alert=True)
            return
        deal["buyer_confirmed"] = True
    elif role == "seller":
        if user.id != deal.get("seller_id"):
            await q.answer("❌ You are not the seller.", show_alert=True)
            return
        if deal.get("seller_confirmed"):
            await q.answer("✅ Already confirmed.", show_alert=True)
            return
        deal["seller_confirmed"] = True
    await q.answer(f"✅ {role.capitalize()} confirmed!")
    b = deal["buyer_confirmed"]
    s = deal["seller_confirmed"]
    if b and s:
        await q.edit_message_text("🎉 <b>BOTH CONFIRMED!</b>\n\n✅ Buyer\n✅ Seller\n\n⏳ Processing release…", parse_mode="HTML")
        await release_deal(ctx, did, deal, q.message.chat_id)
    else:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{'✅' if b else '⏳'} Buyer Confirm", callback_data=f"confirm:buyer:{did}"),
             InlineKeyboardButton(f"{'✅' if s else '⏳'} Seller Confirm", callback_data=f"confirm:seller:{did}")],
            [InlineKeyboardButton("🚨 Dispute / Call Admin", callback_data="dispute_call")]
        ])
        await q.edit_message_text(
            f"📊 <b>CONFIRMATION STATUS</b>\n\n"
            f"🛒 Buyer: {'✅ Confirmed' if b else '⏳ Waiting'}\n"
            f"🏪 Seller: {'✅ Confirmed' if s else '⏳ Waiting'}\n\n"
            f"⚠️ Both must confirm for release.",
            reply_markup=kb, parse_mode="HTML"
        )

# ══════════════════════════════════════════════════════════
# STEP 9: RELEASE
# ══════════════════════════════════════════════════════════

async def release_deal(ctx, did, deal, group_id):
    apply_fee = True
    if state.required_bio:
        try:
            buyer_chat = await ctx.bot.get_chat(deal.get("buyer_id"))
            bio = getattr(buyer_chat, "bio", "") or ""
            if state.required_bio.lower() in bio.lower():
                apply_fee = False
        except Exception:
            pass
    qty     = float(deal.get("quantity", 0))
    fee_amt = qty * (state.fee_percent / 100) if apply_fee else 0.0
    final   = qty - fee_amt
    deal.update({"status": "COMPLETED", "final_amount": final,
                 "fee_deducted": fee_amt, "completed_at": datetime.utcnow().isoformat()})
    try:
        await ctx.bot.send_message(
            chat_id=group_id,
            text=(
                f"🎉 <b>DEAL COMPLETED!</b>\n\n🆔 <code>{did}</code>\n🪙 {deal.get('token')}\n"
                f"💰 Original: {qty}\n💸 Fee ({state.fee_percent}%): {fee_amt:.4f}\n"
                f"✅ Final: {final:.4f}\n\n"
                f"🛒 @{deal.get('buyer_username')}  🏪 @{deal.get('seller_username')}\n\n"
                f"📊 COMPLETED\n⏰ {deal['completed_at']}\n\nThank you! 🙏"
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await log(ctx,
        f"✅ <b>DEAL COMPLETED</b>\n\n🆔 <code>{did}</code>\n"
        f"🛒 @{deal.get('buyer_username')}  🏪 @{deal.get('seller_username')}\n"
        f"🪙 {deal.get('token')}  💰 {qty}  💸 {fee_amt:.4f}  ✅ {final:.4f}\n"
        f"📦 <code>{group_id}</code>\n📊 COMPLETED\n⏰ {deal['completed_at']}"
    )
    for p in ("buyer", "seller"):
        pid = deal.get(f"{p}_id")
        if pid:
            try:
                await ctx.bot.send_message(
                    chat_id=pid,
                    text=f"✅ <b>Deal Completed: {did}</b>\n\nFinal: <b>{final:.4f} {deal.get('token')}</b>\nGroup closes shortly.",
                    parse_mode="HTML"
                )
            except Exception:
                pass
    await asyncio.sleep(10)
    try:
        await ctx.bot.send_message(chat_id=group_id, text="🗑 <b>Group closing in 10 seconds. Thank you!</b>", parse_mode="HTML")
        await asyncio.sleep(10)
        await ctx.bot.leave_chat(group_id)
        await delete_group_telethon(group_id)
    except Exception:
        pass

# ══════════════════════════════════════════════════════════
# STEP 10: /dispute
# ══════════════════════════════════════════════════════════

async def cmd_dispute(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if chat.type == "private":
        await update.message.reply_text("❌ Use inside your deal group.")
        return
    did, deal = deal_by_group(chat.id)
    if not deal:
        await update.message.reply_text("❌ No active deal here.")
        return
    if deal.get("status") == "COMPLETED":
        await update.message.reply_text("❌ Cannot dispute completed deal.")
        return
    if deal.get("status") == "DISPUTED":
        await update.message.reply_text("⚠️ Dispute already open.")
        return
    reason = " ".join(ctx.args) if ctx.args else "No reason provided"
    deal.update({"status": "DISPUTED", "dispute_by": user.username or user.first_name,
                 "dispute_reason": reason, "dispute_at": datetime.utcnow().isoformat()})
    await update.message.reply_text(
        f"🚨 <b>DISPUTE TRIGGERED!</b>\n\n👤 @{deal['dispute_by']}\n📝 {reason}\n\n⏳ Admin will join shortly.",
        parse_mode="HTML"
    )
    group_link = f"https://t.me/c/{str(chat.id).replace('-100','')}/1"
    await alert_admins(ctx,
        f"🚨 <b>DISPUTE ALERT!</b>\n\n🆔 <code>{did}</code>\n"
        f"🛒 @{deal.get('buyer_username','N/A')}  🏪 @{deal.get('seller_username','N/A')}\n"
        f"⚠️ By: @{deal['dispute_by']}\n📝 {reason}\n🔗 {group_link}\n⏰ {deal['dispute_at']}",
        deal_id=did
    )
    await log(ctx,
        f"⚠️ <b>DISPUTE OPENED</b>\n\n🆔 <code>{did}</code>\n"
        f"⚠️ @{deal['dispute_by']}\n📝 {reason}\n📦 <code>{chat.id}</code>\n📊 DISPUTED\n⏰ {deal['dispute_at']}"
    )

async def handle_dispute_call(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    chat_id = q.message.chat_id
    did, deal = deal_by_group(chat_id)
    if not deal:
        await q.answer("❌ No active deal.", show_alert=True)
        return
    if deal.get("status") == "DISPUTED":
        await q.answer("⚠️ Dispute already open.", show_alert=True)
        return
    user = q.from_user
    deal.update({"status": "DISPUTED", "dispute_by": user.username or user.first_name,
                 "dispute_reason": "Via inline button", "dispute_at": datetime.utcnow().isoformat()})
    await q.edit_message_text("🚨 <b>DISPUTE TRIGGERED!</b>\n\nAdmin notified. Please remain in the group.", parse_mode="HTML")
    group_link = f"https://t.me/c/{str(chat_id).replace('-100','')}/1"
    await alert_admins(ctx,
        f"🚨 <b>DISPUTE ALERT!</b>\n\n🆔 <code>{did}</code>\n"
        f"🛒 @{deal.get('buyer_username','N/A')}  🏪 @{deal.get('seller_username','N/A')}\n"
        f"⚠️ By: @{deal['dispute_by']}\n🔗 {group_link}",
        deal_id=did
    )
    await log(ctx, f"⚠️ <b>DISPUTE OPENED</b>\n\n🆔 <code>{did}</code>\n📊 DISPUTED\n⏰ {deal['dispute_at']}")

async def handle_dispute_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE, d: str):
    q = update.callback_query
    user = q.from_user
    did = d.split(":")[1]
    if not is_admin(user.id):
        await q.answer("❌ Not authorized.", show_alert=True)
        return
    deal = deal_by_id(did)
    if not deal:
        await q.answer("❌ Deal not found.", show_alert=True)
        return
    if did in state.dispute_admins and state.dispute_admins[did] != user.id:
        await q.answer("❌ Another admin is already handling this.", show_alert=True)
        return
    state.dispute_admins[did] = user.id
    await q.edit_message_text(
        f"✅ <b>You are handling this dispute.</b>\n\n🆔 <code>{did}</code>\n"
        f"🛒 @{deal.get('buyer_username')}  🏪 @{deal.get('seller_username')}\n\n"
        f"Commands:\n<code>/releaseto buyer {did}</code>\n"
        f"<code>/releaseto seller {did}</code>\n<code>/canceldeal {did}</code>",
        parse_mode="HTML"
    )
    try:
        await ctx.bot.send_message(
            chat_id=deal["group_id"],
            text=f"👨‍💼 <b>Admin @{user.username or 'Admin'} joined.</b>\nHandling dispute. <b>Other admins cannot join.</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass

# ══════════════════════════════════════════════════════════
# ADMIN COMMANDS
# ══════════════════════════════════════════════════════════

async def cmd_setloggroup(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if not is_main_admin(user.id):
        return
    if chat.type == "private":
        await update.message.reply_text("❌ Run this inside the group you want as LOG GROUP.")
        return
    state.log_group_id = chat.id
    await update.message.reply_text(f"✅ <b>LOG GROUP SET!</b>\n\n📋 {chat.title}\n🆔 <code>{chat.id}</code>\n\nBot ready for deals!", parse_mode="HTML")

async def cmd_addadmin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_main_admin(update.effective_user.id):
        return
    if not ctx.args:
        await update.message.reply_text("Usage: <code>/addadmin {user_id}</code>", parse_mode="HTML")
        return
    try:
        uid = int(ctx.args[0])
        state.sub_admins.add(uid)
        await update.message.reply_text(f"✅ Sub Admin Added: <code>{uid}</code>", parse_mode="HTML")
        try:
            await ctx.bot.send_message(chat_id=uid, text="👨‍💼 <b>You've been added as Sub Admin!</b>", parse_mode="HTML")
        except Exception:
            pass
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.")

async def cmd_removeadmin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_main_admin(update.effective_user.id):
        return
    if not ctx.args:
        await update.message.reply_text("Usage: <code>/removeadmin {user_id}</code>", parse_mode="HTML")
        return
    try:
        state.sub_admins.discard(int(ctx.args[0]))
        await update.message.reply_text(f"✅ Removed <code>{ctx.args[0]}</code>", parse_mode="HTML")
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.")

async def cmd_setfee(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_main_admin(update.effective_user.id):
        return
    if not ctx.args:
        await update.message.reply_text(f"Usage: <code>/setfee {{percent}}</code>\nCurrent: <b>{state.fee_percent}%</b>", parse_mode="HTML")
        return
    try:
        fee = float(ctx.args[0])
        if not (0 <= fee <= 50):
            await update.message.reply_text("❌ Fee must be 0–50%.")
            return
        old = state.fee_percent
        state.fee_percent = fee
        await update.message.reply_text(f"✅ Fee updated: <s>{old}%</s> → <b>{fee}%</b>", parse_mode="HTML")
    except ValueError:
        await update.message.reply_text("❌ Invalid number.")

async def cmd_setbio(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_main_admin(update.effective_user.id):
        return
    if not ctx.args:
        await update.message.reply_text(f"Usage: <code>/setbio {{tag}}</code>\nCurrent: <b>{state.required_bio or 'Not set'}</b>", parse_mode="HTML")
        return
    state.required_bio = ctx.args[0]
    await update.message.reply_text(f"✅ Bio tag set: <b>{state.required_bio}</b>\nUsers with this in bio → 0% fee.", parse_mode="HTML")

async def cmd_setoxapay(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_main_admin(update.effective_user.id):
        return
    if not ctx.args:
        await update.message.reply_text("Usage: <code>/setoxapay {api_key}</code>", parse_mode="HTML")
        return
    state.oxapay_key = ctx.args[0]
    key = state.oxapay_key
    masked = f"{key[:4]}{'*'*(len(key)-8)}{key[-4:]}" if len(key) > 8 else "****"
    await update.message.reply_text(f"✅ <b>OxaPay Key Set!</b>\n🔑 <code>{masked}</code>\n\nUse /checkoxapay to verify.", parse_mode="HTML")

async def cmd_checkoxapay(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_main_admin(update.effective_user.id):
        return
    if not state.oxapay_key:
        await update.message.reply_text("❌ OxaPay key not set.")
        return
    await update.message.reply_text("⏳ Checking…")
    try:
        data = await async_post("https://api.oxapay.com/merchants/balance", {"merchant": state.oxapay_key})
        if data.get("result") == 100:
            bal = data.get("balance", {})
            bal_txt = "\n".join(f"  • {k}: {v}" for k, v in bal.items()) if bal else "N/A"
            await update.message.reply_text(f"✅ <b>OxaPay Connected!</b>\n\n💰 Balances:\n{bal_txt}", parse_mode="HTML")
        else:
            await update.message.reply_text(f"⚠️ Error: {data.get('message')}")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {e}")

async def cmd_resetoxapay(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_main_admin(update.effective_user.id):
        return
    state.oxapay_key = None
    await update.message.reply_text("✅ OxaPay key removed. Bot in DEMO mode.")

# ── Telethon credentials via bot ──

async def cmd_setapiid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_main_admin(update.effective_user.id):
        return
    if not ctx.args:
        await update.message.reply_text("Usage: <code>/setapiid {api_id}</code>", parse_mode="HTML")
        return
    try:
        state.api_id = int(ctx.args[0])
        await update.message.reply_text(f"✅ API ID set: <code>{state.api_id}</code>\n\nNow set: /setapihash", parse_mode="HTML")
    except ValueError:
        await update.message.reply_text("❌ API ID must be a number.")

async def cmd_setapihash(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_main_admin(update.effective_user.id):
        return
    if not ctx.args:
        await update.message.reply_text("Usage: <code>/setapihash {api_hash}</code>", parse_mode="HTML")
        return
    state.api_hash = ctx.args[0]
    await update.message.reply_text(f"✅ API Hash set.\n\nNow set: /setphone", parse_mode="HTML")

async def cmd_setphone(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_main_admin(update.effective_user.id):
        return
    if not ctx.args:
        await update.message.reply_text("Usage: <code>/setphone +1234567890</code>", parse_mode="HTML")
        return
    state.phone = ctx.args[0]
    await update.message.reply_text(f"✅ Phone set: <code>{state.phone}</code>\n\nNow run: /starttelethon", parse_mode="HTML")

async def cmd_starttelethon(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_main_admin(update.effective_user.id):
        return
    if not state.api_id or not state.api_hash or not state.phone:
        await update.message.reply_text(
            "❌ Set all credentials first:\n\n"
            "<code>/setapiid YOUR_API_ID</code>\n"
            "<code>/setapihash YOUR_API_HASH</code>\n"
            "<code>/setphone +1234567890</code>",
            parse_mode="HTML"
        )
        return
    await update.message.reply_text("⏳ Connecting Telethon…\n\n⚠️ Check your Telegram app for OTP code.\nSend it here as: <code>/otp 12345</code>", parse_mode="HTML")
    try:
        client = TelegramClient("escrow_session", int(state.api_id), state.api_hash)
        state._pending_telethon = client
        await client.connect()
        if not await client.is_user_authorized():
            await client.send_code_request(state.phone)
            state._waiting_otp = True
            await update.message.reply_text("📲 OTP sent to your phone!\n\nSend it as: <code>/otp YOUR_CODE</code>", parse_mode="HTML")
        else:
            state.telethon_client = client
            state._waiting_otp = False
            await update.message.reply_text("✅ <b>Telethon Connected!</b>\n\nAuto group creation is now active.", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Telethon failed: {e}")

async def cmd_otp(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_main_admin(update.effective_user.id):
        return
    if not ctx.args:
        await update.message.reply_text("Usage: <code>/otp 12345</code>", parse_mode="HTML")
        return
    if not getattr(state, "_waiting_otp", False) or not getattr(state, "_pending_telethon", None):
        await update.message.reply_text("❌ No pending OTP. Run /starttelethon first.")
        return
    try:
        client = state._pending_telethon
        await client.sign_in(state.phone, ctx.args[0])
        state.telethon_client = client
        state._waiting_otp = False
        state._pending_telethon = None
        await update.message.reply_text("✅ <b>Telethon Connected!</b>\n\nAuto group creation is now ACTIVE! 🎉", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ OTP failed: {e}\n\nTry /starttelethon again.")

# ── Dispute & deal management ──

async def cmd_releaseto(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(ctx.args) < 2:
        await update.message.reply_text("Usage: <code>/releaseto buyer|seller DEAL_ID</code>", parse_mode="HTML")
        return
    party = ctx.args[0].lower()
    did   = ctx.args[1].upper()
    if party not in ("buyer", "seller"):
        await update.message.reply_text("❌ Must be buyer or seller.")
        return
    deal = deal_by_id(did)
    if not deal:
        await update.message.reply_text(f"❌ Not found: <code>{did}</code>", parse_mode="HTML")
        return
    if deal.get("status") == "COMPLETED":
        await update.message.reply_text("⚠️ Already completed.")
        return
    user = update.effective_user
    assigned = state.dispute_admins.get(did)
    if assigned and assigned != user.id and not is_main_admin(user.id):
        await update.message.reply_text("❌ Another admin is handling this dispute.")
        return
    qty     = float(deal.get("quantity", 0))
    fee_amt = qty * (state.fee_percent / 100)
    final   = qty - fee_amt
    to_user = deal.get(f"{party}_username", "N/A")
    to_addr = deal.get(f"{party}_address", "N/A")
    deal.update({"status": "COMPLETED", "force_released_to": party,
                 "fee_deducted": fee_amt, "final_amount": final,
                 "completed_at": datetime.utcnow().isoformat()})
    try:
        await ctx.bot.send_message(
            chat_id=deal["group_id"],
            text=(
                f"⚖️ <b>ADMIN DECISION</b>\n\n👨‍💼 @{user.username}\n⚖️ Released to: <b>{party.upper()}</b>\n\n"
                f"🆔 <code>{did}</code>\n🪙 {deal.get('token')}\n"
                f"💰 {qty}  💸 {fee_amt:.4f}  ✅ {final:.4f}\n"
                f"👤 @{to_user}\n📬 <code>{to_addr}</code>\n\n📊 COMPLETED — Group closes shortly."
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await update.message.reply_text(f"✅ Force Released to <b>{party.upper()}</b> (@{to_user}) — {final:.4f}", parse_mode="HTML")
    await log(ctx,
        f"⚖️ <b>ADMIN FORCE RELEASE</b>\n\n🆔 <code>{did}</code>\n⚖️ {party.upper()} (@{to_user})\n"
        f"🪙 {deal.get('token')}  ✅ {final:.4f}\n👨‍💼 @{user.username}\n📊 COMPLETED (Force)\n⏰ {deal['completed_at']}"
    )
    await asyncio.sleep(15)
    try:
        await ctx.bot.leave_chat(deal["group_id"])
        await delete_group_telethon(deal["group_id"])
    except Exception:
        pass

async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    all_d = list(state.deals.values())
    total = len(all_d)
    done  = sum(1 for x in all_d if x["status"] == "COMPLETED")
    dis   = sum(1 for x in all_d if x["status"] == "DISPUTED")
    fund  = sum(1 for x in all_d if x["status"] == "FUNDED")
    ox = f"✅ {state.oxapay_key[:4]}...{state.oxapay_key[-4:]}" if state.oxapay_key else "❌ Not Set"
    lg = f"✅ <code>{state.log_group_id}</code>" if state.log_group_id else "❌ Not Set"
    tc = "✅ Connected" if state.telethon_client else "❌ Not Connected"
    await update.message.reply_text(
        f"📊 <b>BOT STATUS</b>\n\n📋 {lg}\n🔑 {ox}\n📡 Telethon: {tc}\n"
        f"💸 Fee: <b>{state.fee_percent}%</b>\n🏷 Bio: <b>{state.required_bio or 'Not Set'}</b>\n\n"
        f"📦 Total: {total}  🟢 Active: {total-done}  ✅ Done: {done}\n"
        f"💰 Funded: {fund}  🚨 Disputed: {dis}",
        parse_mode="HTML"
    )

async def cmd_dealinfo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if not ctx.args:
        await update.message.reply_text("Usage: <code>/dealinfo {TRADE_ID}</code>", parse_mode="HTML")
        return
    did  = ctx.args[0].upper()
    deal = deal_by_id(did)
    if not deal:
        await update.message.reply_text(f"❌ Not found: <code>{did}</code>", parse_mode="HTML")
        return
    is_part = user.id in (deal.get("buyer_id"), deal.get("seller_id"))
    in_grp  = state.group_to_deal.get(chat.id) == did
    if not is_admin(user.id) and not is_part and not in_grp:
        await update.message.reply_text("❌ Not authorized.")
        return
    b = "✅" if deal.get("buyer_confirmed") else "⏳"
    s = "✅" if deal.get("seller_confirmed") else "⏳"
    await update.message.reply_text(
        f"📋 <b>DEAL INFO</b>\n\n🆔 <code>{did}</code>  📊 <b>{deal.get('status')}</b>\n\n"
        f"🛒 @{deal.get('buyer_username','—')}  <code>{deal.get('buyer_address','N/A')}</code>\n"
        f"🏪 @{deal.get('seller_username','—')}  <code>{deal.get('seller_address','N/A')}</code>\n\n"
        f"💰 {deal.get('quantity','N/A')}  📈 {deal.get('rate','N/A')}\n📝 {deal.get('condition','—')}\n"
        f"🪙 {deal.get('token','Not Selected')}\n📬 <code>{deal.get('deposit_address','Not Generated')}</code>\n\n"
        f"{b} Buyer  |  {s} Seller\n⏰ {deal.get('created_at','N/A')[:19].replace('T',' ')} UTC",
        parse_mode="HTML"
    )

async def cmd_canceldeal(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_main_admin(update.effective_user.id):
        return
    if not ctx.args:
        await update.message.reply_text("Usage: <code>/canceldeal {TRADE_ID}</code>", parse_mode="HTML")
        return
    did  = ctx.args[0].upper()
    deal = deal_by_id(did)
    if not deal:
        await update.message.reply_text(f"❌ Not found: <code>{did}</code>", parse_mode="HTML")
        return
    if deal.get("status") == "COMPLETED":
        await update.message.reply_text("⚠️ Cannot cancel completed deal.")
        return
    user = update.effective_user
    old = deal["status"]
    deal.update({"status": "CANCELLED", "cancelled_by": user.username, "cancelled_at": datetime.utcnow().isoformat()})
    try:
        await ctx.bot.send_message(chat_id=deal["group_id"], text=f"🚫 <b>DEAL CANCELLED</b>\n\n🆔 <code>{did}</code>\nNo funds transferred.", parse_mode="HTML")
    except Exception:
        pass
    await update.message.reply_text(f"✅ <code>{did}</code> cancelled. Was: {old}", parse_mode="HTML")
    await log(ctx, f"🚫 <b>DEAL CANCELLED</b>\n\n🆔 <code>{did}</code>\n👨‍💼 @{user.username}\n📊 Was: {old}\n⏰ {deal['cancelled_at']}")

async def cmd_listadmins(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_main_admin(update.effective_user.id):
        return
    txt = f"👑 Main: <code>{MAIN_ADMIN_ID}</code>\n\n"
    txt += ("👨‍💼 Sub Admins:\n" + "".join(f"{i}. <code>{a}</code>\n" for i, a in enumerate(state.sub_admins, 1))) if state.sub_admins else "👨‍💼 Sub Admins: None"
    await update.message.reply_text(f"📋 <b>ADMIN LIST</b>\n\n{txt}", parse_mode="HTML")

# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════

async def post_init(app):
    """Try to reconnect Telethon if session file exists from before."""
    if state.api_id and state.api_hash and state.phone:
        await start_telethon()

def main():
    logger.info("Starting P2P Escrow Bot…")
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    handlers = [
        ("start", cmd_start), ("instructions", cmd_instructions),
        ("adminpanel", cmd_adminpanel), ("initdeal", cmd_initdeal),
        ("dd", cmd_dd), ("buyer", cmd_buyer), ("seller", cmd_seller),
        ("token", cmd_token), ("deposit", cmd_deposit), ("verify", cmd_verify),
        ("dispute", cmd_dispute), ("dealinfo", cmd_dealinfo),
        ("setloggroup", cmd_setloggroup), ("addadmin", cmd_addadmin),
        ("removeadmin", cmd_removeadmin), ("setfee", cmd_setfee),
        ("setbio", cmd_setbio), ("setoxapay", cmd_setoxapay),
        ("checkoxapay", cmd_checkoxapay), ("resetoxapay", cmd_resetoxapay),
        ("setapiid", cmd_setapiid), ("setapihash", cmd_setapihash),
        ("setphone", cmd_setphone), ("starttelethon", cmd_starttelethon),
        ("otp", cmd_otp), ("releaseto", cmd_releaseto),
        ("status", cmd_status), ("listadmins", cmd_listadmins),
        ("canceldeal", cmd_canceldeal),
    ]
    for name, func in handlers:
        app.add_handler(CommandHandler(name, func))
    app.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("Bot running…")
    app.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()
