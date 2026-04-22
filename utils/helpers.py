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


def calculate_win_reward(bet_amount: float) -> tuple:
    gross = bet_amount * 2
    profit = gross - bet_amount
    tax = profit * 0.10
    net = gross - tax
    return round(net, 2), round(tax, 2)


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
