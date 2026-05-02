"""
Mines Game
- 5x5 grid = 25 tiles
- Admin sets: min mines (forced 5), max mines, win_rate (house edge)
- Psychology: multiplier grows fast early, but admin-controlled house edge
  means expected value is always negative for user
"""
import random
import json
import uuid
from aiogram.types import Message, CallbackQuery
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import db
from utils.logger import logger
from ui.messages import SEP
from ui.keyboards import back_kb, mines_grid_kb


GRID_SIZE = 25  # 5x5


def calculate_multiplier(mines: int, revealed: int, house_edge_pct: float) -> float:
    """
    Calculate current multiplier based on tiles revealed and mines count.
    Uses probability math with house edge applied.
    Feels rewarding early (fast growth) but house edge ensures casino wins long-term.
    """
    if revealed == 0:
        return 1.0
    safe_tiles = GRID_SIZE - mines
    prob = 1.0
    for i in range(revealed):
        prob *= (safe_tiles - i) / (GRID_SIZE - i)
    # Raw fair multiplier
    fair_mult = 1.0 / prob
    # Apply house edge (reduce payout)
    edge = 1 - (house_edge_pct / 100)
    return round(fair_mult * edge, 4)


async def prompt_mines(message: Message, bet: float):
    """Step 1 — ask how many mines."""
    from ui.keyboards import mines_count_kb
    min_mines = int(await db.get_setting("mines_min_count") or "5")
    max_mines = int(await db.get_setting("mines_max_count") or "23")
    await message.answer(
        f"💣 <b>MINES</b>\n{SEP}\n"
        f"💰 Bet: <b>{bet:,.4f} Tokens</b>\n\n"
        f"🗺 5x5 Grid — 25 tiles\n"
        f"Reveal safe tiles to grow your multiplier!\n"
        f"Hit a mine = lose everything 💥\n\n"
        f"Min mines: <b>{min_mines}</b> | Max: <b>{max_mines}</b>\n\n"
        f"Choose number of mines:",
        parse_mode="HTML",
        reply_markup=mines_count_kb(bet)
    )


async def start_mines(callback: CallbackQuery, bot: Bot, bet: float, mines_count: int):
    """Step 2 — create game, show empty grid."""
    user_id = callback.from_user.id

    min_mines = int(await db.get_setting("mines_min_count") or "5")
    max_mines = int(await db.get_setting("mines_max_count") or "23")

    if mines_count < min_mines or mines_count > max_mines:
        await callback.answer(f"Mines must be {min_mines}-{max_mines}!", show_alert=True)
        return

    user = await db.get_user(user_id)
    if not user or user["token_balance"] < bet:
        await callback.answer("Insufficient Tokens!", show_alert=True); return
    if await db.is_balance_locked(user_id):
        await callback.answer("Game in progress!", show_alert=True); return

    await db.lock_balance(user_id, bet)

    # Generate mine positions — admin-controlled house edge affects win_rate
    # Place mines randomly across 25 tiles
    mine_positions = random.sample(range(GRID_SIZE), mines_count)

    game_id = str(uuid.uuid4())[:8]
    game_state = {
        "bet": bet,
        "mines": mines_count,
        "mine_positions": mine_positions,
        "revealed": [],
        "user_id": user_id,
        "active": True,
    }
    # Store game state in DB
    await db.set_setting(f"mines_game_{game_id}", json.dumps(game_state))

    house_edge = float(await db.get_setting("mines_house_edge") or "5")
    mult = calculate_multiplier(mines_count, 0, house_edge)

    await callback.message.edit_text(
        f"💣 <b>MINES</b>\n{SEP}\n"
        f"💰 Bet: <b>{bet:,.4f} Tokens</b> | 💣 Mines: <b>{mines_count}</b>\n"
        f"📈 Multiplier: <b>{mult}x</b>\n"
        f"💵 Cashout: <b>{round(bet * mult, 4):,.4f}</b>\n\n"
        f"Tap a tile to reveal it!",
        parse_mode="HTML",
        reply_markup=mines_grid_kb(bet, mines_count, [], game_id)
    )
    await callback.answer()
    logger.info(f"Mines started | user={user_id} | bet={bet} | mines={mines_count} | game={game_id}")


async def reveal_tile(callback: CallbackQuery, bot: Bot, game_id: str, tile_idx: int):
    """User tapped a tile — reveal it."""
    user_id = callback.from_user.id
    raw = await db.get_setting(f"mines_game_{game_id}")
    if not raw:
        await callback.answer("Game not found!", show_alert=True); return

    game = json.loads(raw)
    if game["user_id"] != user_id:
        await callback.answer("Not your game!", show_alert=True); return
    if not game["active"]:
        await callback.answer("Game already ended!", show_alert=True); return
    if tile_idx in game["revealed"]:
        await callback.answer("Already revealed!", show_alert=True); return

    house_edge = float(await db.get_setting("mines_house_edge") or "5")
    bet = game["bet"]
    mines_count = game["mines"]

    # Check if mine
    if tile_idx in game["mine_positions"]:
        # BOOM — lose
        game["active"] = False
        await db.set_setting(f"mines_game_{game_id}", json.dumps(game))
        await db.unlock_balance(user_id)
        await db.update_token_balance(user_id, -bet)
        await db.update_wagered(user_id, bet)
        await db.add_transaction(user_id, "loss", bet, currency="TOKEN")

        # Show all mines on grid
        all_revealed = game["revealed"] + [tile_idx]
        # Build exploded grid showing mine positions
        builder = InlineKeyboardBuilder()
        for i in range(GRID_SIZE):
            if i in game["mine_positions"]:
                builder.button(text="💣", callback_data=f"mines_dead_{i}")
            elif i in all_revealed:
                builder.button(text="✅", callback_data=f"mines_dead_{i}")
            else:
                builder.button(text="⬜", callback_data=f"mines_dead_{i}")
        builder.adjust(5)
        builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="menu_games"))

        user = await db.get_user(user_id)
        await callback.message.edit_text(
            f"💣 <b>MINES</b>\n{SEP}\n"
            f"💰 Bet: <b>{bet:,.4f} Tokens</b> | 💣 Mines: <b>{mines_count}</b>\n\n"
            f"💥 <b>BOOM! You hit a mine!</b>\n"
            f"💸 Lost: <b>-{bet:,.4f} Tokens</b>\n"
            f"{SEP}\n🪙 Balance: <b>{user['token_balance']:,.4f}</b>",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
        await callback.answer("💥 BOOM!", show_alert=False)
        logger.info(f"Mines BOOM | user={user_id} | game={game_id} | tile={tile_idx}")
        return

    # Safe tile
    game["revealed"].append(tile_idx)
    await db.set_setting(f"mines_game_{game_id}", json.dumps(game))

    revealed_count = len(game["revealed"])
    mult = calculate_multiplier(mines_count, revealed_count, house_edge)
    cashout_val = round(bet * mult, 4)

    await callback.message.edit_text(
        f"💣 <b>MINES</b>\n{SEP}\n"
        f"💰 Bet: <b>{bet:,.4f} Tokens</b> | 💣 Mines: <b>{mines_count}</b>\n"
        f"✅ Safe tiles: <b>{revealed_count}</b>\n"
        f"📈 Multiplier: <b>{mult}x</b>\n"
        f"💵 Cashout now: <b>{cashout_val:,.4f}</b>\n\n"
        f"Keep going or cashout?",
        parse_mode="HTML",
        reply_markup=mines_grid_kb(bet, mines_count, game["revealed"], game_id)
    )
    await callback.answer(f"✅ Safe! {mult}x")
    logger.info(f"Mines safe tile | user={user_id} | game={game_id} | tile={tile_idx} | mult={mult}x")


async def cashout_mines(callback: CallbackQuery, bot: Bot, game_id: str):
    """User cashes out — pay winnings."""
    user_id = callback.from_user.id
    raw = await db.get_setting(f"mines_game_{game_id}")
    if not raw:
        await callback.answer("Game not found!", show_alert=True); return

    game = json.loads(raw)
    if game["user_id"] != user_id:
        await callback.answer("Not your game!", show_alert=True); return
    if not game["active"]:
        await callback.answer("Game already ended!", show_alert=True); return
    if not game["revealed"]:
        await callback.answer("Reveal at least 1 tile before cashing out!", show_alert=True); return

    house_edge = float(await db.get_setting("mines_house_edge") or "5")
    tax_pct = float(await db.get_setting("game_tax_percent") or "5")
    bet = game["bet"]
    mines_count = game["mines"]
    revealed_count = len(game["revealed"])

    mult = calculate_multiplier(mines_count, revealed_count, house_edge)
    gross = round(bet * mult, 4)
    tax = round(gross * tax_pct / 100, 4)
    reward = round(gross - tax, 4)

    game["active"] = False
    await db.set_setting(f"mines_game_{game_id}", json.dumps(game))

    await db.unlock_balance(user_id)
    await db.update_token_balance(user_id, reward - bet)
    await db.update_wagered(user_id, bet)
    await db.add_transaction(user_id, "win", reward, currency="TOKEN")

    user = await db.get_user(user_id)
    await callback.message.edit_text(
        f"💣 <b>MINES</b>\n{SEP}\n"
        f"💰 Bet: <b>{bet:,.4f} Tokens</b> | 💣 Mines: <b>{mines_count}</b>\n"
        f"✅ Tiles revealed: <b>{revealed_count}</b>\n"
        f"📈 Multiplier: <b>{mult}x</b>\n\n"
        f"🎉 <b>CASHOUT!</b>\n"
        f"Gross: {gross:,.4f} | Tax: -{tax:,.4f}\n"
        f"✅ +<b>{reward:,.4f} Tokens</b>\n"
        f"{SEP}\n🪙 Balance: <b>{user['token_balance']:,.4f}</b>",
        parse_mode="HTML",
        reply_markup=back_kb("menu_games")
    )
    await callback.answer(f"💰 Cashed out {reward:,.4f}!")
    logger.info(f"Mines cashout | user={user_id} | game={game_id} | mult={mult}x | reward={reward}")
