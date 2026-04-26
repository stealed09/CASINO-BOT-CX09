"""
Provably Fair System
Each game result is generated from:
  server_seed (bot's secret, hashed shown to user upfront)
  client_seed (user chosen or auto-generated)
  nonce       (increments per bet)

Result = HMAC-SHA256(server_seed, client_seed:nonce)
User can verify AFTER game reveals server_seed.
"""

import hmac
import hashlib
import secrets
import aiosqlite
from typing import Tuple, Optional


def generate_server_seed() -> str:
    return secrets.token_hex(32)


def hash_server_seed(server_seed: str) -> str:
    return hashlib.sha256(server_seed.encode()).hexdigest()


def generate_client_seed() -> str:
    return secrets.token_hex(8)


def generate_result(server_seed: str, client_seed: str, nonce: int) -> float:
    """
    Returns a float 0.0–1.0 deterministically from the seeds.
    Game logic maps this to actual game outcome.
    """
    msg = f"{client_seed}:{nonce}".encode()
    key = server_seed.encode()
    h = hmac.new(key, msg, hashlib.sha256).hexdigest()
    # Use first 8 hex chars → integer → divide by max
    value = int(h[:8], 16)
    return value / 0xFFFFFFFF


def result_to_dice(result: float) -> int:
    """Map 0–1 result to dice 1–6."""
    return int(result * 6) + 1


def result_to_limbo_multiplier(result: float, house_edge: float = 0.01) -> float:
    """Map 0–1 result to limbo multiplier. House edge applied."""
    if result >= 1 - house_edge:
        return 1.0  # house win
    return round(1.0 / (1.0 - result) * (1 - house_edge), 2)


def result_to_coinflip(result: float) -> str:
    return "heads" if result < 0.5 else "tails"


def result_to_crash(result: float, house_edge: float = 0.04) -> float:
    """Generate crash point. Min 1.0x."""
    if result < house_edge:
        return 1.0
    return round((1 - house_edge) / (1 - result), 2)


def verify_result(server_seed: str, client_seed: str, nonce: int, expected_result: float) -> bool:
    return abs(generate_result(server_seed, client_seed, nonce) - expected_result) < 1e-9


# ── DB helpers ─────────────────────────────────────────────────────────────────

async def get_or_create_seed_pair(user_id: int, db_path: str) -> Tuple[str, str, int]:
    """Return (server_seed, client_seed, nonce) for user. Creates if missing."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT server_seed, client_seed, nonce FROM provably_fair WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        if row:
            return row["server_seed"], row["client_seed"], row["nonce"]
        # Create new
        ss = generate_server_seed()
        cs = generate_client_seed()
        await db.execute(
            "INSERT INTO provably_fair (user_id, server_seed, client_seed, nonce) VALUES (?,?,?,0)",
            (user_id, ss, cs)
        )
        await db.commit()
        return ss, cs, 0


async def increment_nonce(user_id: int, db_path: str):
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE provably_fair SET nonce = nonce + 1 WHERE user_id=?", (user_id,)
        )
        await db.commit()


async def rotate_server_seed(user_id: int, db_path: str) -> Tuple[str, str]:
    """Rotate to new server seed (reveals old one). Returns (old_seed, new_hash)."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT server_seed FROM provably_fair WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        old_seed = row["server_seed"] if row else ""
        new_seed = generate_server_seed()
        new_cs = generate_client_seed()
        await db.execute("""
            INSERT INTO provably_fair (user_id, server_seed, client_seed, nonce)
            VALUES (?,?,?,0)
            ON CONFLICT(user_id) DO UPDATE SET
                server_seed=excluded.server_seed,
                client_seed=excluded.client_seed,
                nonce=0
        """, (user_id, new_seed, new_cs))
        await db.commit()
    return old_seed, hash_server_seed(new_seed)


async def set_client_seed(user_id: int, client_seed: str, db_path: str):
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE provably_fair SET client_seed=?, nonce=0 WHERE user_id=?",
            (client_seed, user_id)
        )
        await db.commit()


def provably_fair_info_text(server_seed_hash: str, client_seed: str, nonce: int) -> str:
    SEP = "─" * 24
    return (
        f"🔐 <b>PROVABLY FAIR</b>\n{SEP}\n"
        f"🔒 Server Seed Hash:\n<code>{server_seed_hash}</code>\n\n"
        f"🎯 Client Seed:\n<code>{client_seed}</code>\n\n"
        f"🔢 Nonce: <b>{nonce}</b>\n"
        f"{SEP}\n"
        f"After each game, verify your result at:\n"
        f"<code>HMAC-SHA256(server_seed, client_seed:nonce)</code>\n"
        f"Use /verify to reveal your server seed & check results."
    )
