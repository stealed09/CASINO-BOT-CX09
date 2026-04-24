"""
Oxapay.com crypto payment integration — No KYC required.
Docs: https://docs.oxapay.com
"""
import aiohttp
from typing import Optional, Dict
from utils.logger import logger

# ── CONFIG — Admin sets MERCHANT_KEY via /aset_oxapay_key ─────────────────────
_BASE_URL    = "https://api.oxapay.com"
_MERCHANT_KEY = "ZVPRPD-BQAIMR-HTQE1F-CG1HUY"  # live key

def _get_key() -> str:
    return _MERCHANT_KEY

def set_merchant_key(key: str):
    global _MERCHANT_KEY
    _MERCHANT_KEY = key


# ── SUPPORTED CURRENCIES ──────────────────────────────────────────────────────
OXAPAY_CURRENCIES = [
    ("USDT (TRC20)", "USDT",  "TRC20"),
    ("USDT (ERC20)", "USDT",  "ERC20"),
    ("USDT (BEP20)", "USDT",  "BEP20"),
    ("Bitcoin",      "BTC",   "BTC"),
    ("Ethereum",     "ETH",   "ERC20"),
    ("Litecoin",     "LTC",   "LTC"),
    ("TRON",         "TRX",   "TRC20"),
    ("Dogecoin",     "DOGE",  "DOGE"),
    ("BNB",          "BNB",   "BEP20"),
]


# ── API CALLS ──────────────────────────────────────────────────────────────────

async def create_invoice(amount_usd: float, currency: str, network: str,
                          order_id: str, description: str) -> Optional[Dict]:
    """
    Create a payment invoice on Oxapay.
    Returns dict with payAddress, amount, trackId, etc.
    """
    payload = {
        "merchant": _get_key(),
        "amount": round(amount_usd, 2),
        "currency": "USD",
        "payCurrency": currency,
        "network": network,
        "orderId": order_id,
        "description": description,
        "feePaidByPayer": 0,
        "underPaidCover": 2.5,   # allow 2.5% underpayment
        "lifeTime": 60,          # 60 minutes expiry
        "callbackUrl": "",
        "returnUrl": "",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{_BASE_URL}/merchants/request",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                data = await resp.json()
                logger.info(f"Oxapay create_invoice [{resp.status}]: {data}")
                if data.get("result") == 100:
                    return data
                logger.error(f"Oxapay error: {data}")
                return None
    except Exception as e:
        logger.error(f"Oxapay create_invoice exception: {e}")
        return None


async def check_payment(track_id: str) -> Optional[Dict]:
    """Check payment status by trackId."""
    payload = {
        "merchant": _get_key(),
        "trackId": track_id,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{_BASE_URL}/merchants/inquiry",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                data = await resp.json()
                if data.get("result") == 100:
                    return data
                return None
    except Exception as e:
        logger.error(f"Oxapay check_payment exception: {e}")
        return None


# Oxapay payment statuses
# Waiting   — waiting for payment
# Confirming — tx found, waiting confirmations
# Paid      — confirmed, credit user
# Expired   — not paid in time
# Error     — something went wrong

PAID_STATUSES    = {"Paid"}
FAILED_STATUSES  = {"Expired", "Error"}
