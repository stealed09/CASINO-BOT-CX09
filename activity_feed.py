"""
Live Activity Feed
Shows recent wins/activity across the casino.
Mix of real and fake entries for "busy casino" feel.
"""

import random
from collections import deque
from datetime import datetime
from typing import List, Optional

SEP = "─" * 24

# Rolling buffer of last 20 real events
_feed: deque = deque(maxlen=20)

FAKE_NAMES = [
    "Arjun🎰", "Priya💎", "RajKing", "Lucky77", "Sneha_W",
    "Vikram🔥", "AkshaY", "Divya⭐", "Rohit💰", "Neha🌟",
    "Karan🎲", "Pooja🍀", "Amit🏆", "Riya✨", "Suresh🎯",
]

FAKE_GAMES = ["Crash", "Dice", "Limbo", "Slots", "Coinflip", "High Roll"]

FAKE_TEMPLATES = [
    "{name} hit {mult}x on {game}! 🔥",
    "{name} won {amount} Tokens on {game} 🎉",
    "{name} opened Legendary Case 🌟",
    "{name} joined — VIP Gold 🥇",
    "{name} cashed out at {mult}x Crash 🚀",
    "{name} hit jackpot on Slots! 💎",
]


def add_real_event(user_name: str, game: str, amount: float, event_type: str = "win"):
    icons = {"win": "🏆", "jackpot": "💎", "case": "📦", "vip": "⭐", "rain": "🌧️"}
    icon = icons.get(event_type, "🎰")
    _feed.appendleft({
        "text": f"{icon} <b>{user_name}</b> won <b>{amount:,.0f}</b> on {game}",
        "time": datetime.now().strftime("%H:%M"),
        "real": True,
    })


def _fake_event() -> dict:
    name = random.choice(FAKE_NAMES)
    game = random.choice(FAKE_GAMES)
    template = random.choice(FAKE_TEMPLATES)
    mult = round(random.uniform(1.5, 20.0), 1)
    amount = random.randint(500, 50000)
    text = template.format(name=name, game=game, mult=f"{mult}x", amount=f"{amount:,}")
    return {
        "text": f"🎰 {text}",
        "time": datetime.now().strftime("%H:%M"),
        "real": False,
    }


def get_feed(n: int = 10, mix_fake: bool = True) -> List[dict]:
    """Return last n feed items, optionally mixed with fake entries."""
    real = list(_feed)[:n]
    if not mix_fake or len(real) >= n:
        return real[:n]
    # Fill remaining with fake
    needed = n - len(real)
    fakes = [_fake_event() for _ in range(needed)]
    combined = real + fakes
    random.shuffle(combined)
    return combined[:n]


def feed_text(n: int = 8, mix_fake: bool = True) -> str:
    items = get_feed(n, mix_fake)
    if not items:
        return f"📡 <b>LIVE FEED</b>\n{SEP}\nNo activity yet."
    lines = [f"📡 <b>LIVE CASINO FEED</b>\n{SEP}"]
    for item in items:
        lines.append(f"[{item['time']}] {item['text']}")
    return "\n".join(lines)
