from datetime import datetime
from config import REFERRAL_PERCENT
from utils.logger import logger


def format_balance(amount: float) -> str:
    return f"₹{amount:,.2f}"


def format_date(date_str: str) -> str:
    try:
        dt = datetime.fromisoformat(date_str)
        return dt.strftime("%d %b %Y, %I:%M %p")
    except:
        return date_str


def calculate_referral_bonus(bet_amount: float) -> float:
    return round(bet_amount * REFERRAL_PERCENT * 0.01, 4)


def calculate_win_reward(bet_amount: float, tax_pct: float = 10.0) -> tuple:
    """Apply admin-configurable tax on gross win (2x multiplier)."""
    gross = round(bet_amount * 2, 4)
    tax = round(gross * tax_pct / 100, 4)
    net = round(gross - tax, 4)
    return net, tax


def validate_amount(amount_str: str) -> tuple:
    try:
        amount = float(amount_str)
        if amount <= 0:
            return None, "Amount must be positive."
        if amount > 1_000_000:
            return None, "Amount too large."
        return round(amount, 2), None
    except ValueError:
        return None, "Invalid amount. Please enter a number."
