"""
NowPayments.io LIVE integration.
"""
import aiohttp
import hashlib
import hmac
from typing import Optional, Dict
from utils.logger import logger

# ── LIVE CONFIG ────────────────────────────────────────────────────────────────
SANDBOX      = False
_LIVE_KEY    = "VWZATYB-M2TM9YM-NBM00FA-N10NK8Z"
_LIVE_URL    = "https://api.nowpayments.io/v1"

def _api_key() -> str:
    return _LIVE_KEY

def _base_url() -> str:
    return _LIVE_URL

def _headers() -> dict:
    return {"x-api-key": _api_key(), "Content-Type": "application/json"}


# ── API CALLS ──────────────────────────────────────────────────────────────────

async def create_payment(pay_currency: str, price_amount: float,
                          order_id: str, order_description: str) -> Optional[Dict]:
    payload = {
        "price_amount": price_amount,
        "price_currency": "usd",
        "pay_currency": pay_currency.lower(),
        "order_id": order_id,
        "order_description": order_description,
        "ipn_callback_url": "",
        "is_fixed_rate": False,
        "is_fee_paid_by_user": False,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{_base_url()}/payment",
                headers=_headers(),
                json=payload,
                timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                data = await resp.json()
                logger.info(f"NowPayments [{resp.status}]: {data}")
                if resp.status == 201:
                    return data
                logger.error(f"NowPayments error {resp.status}: {data}")
                return None
    except Exception as e:
        logger.error(f"NowPayments exception: {e}")
        return None


async def get_payment_status(payment_id: str) -> Optional[Dict]:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{_base_url()}/payment/{payment_id}",
                headers=_headers(),
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
    except Exception as e:
        logger.error(f"NowPayments get_status exception: {e}")
        return None


async def get_available_currencies() -> list:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{_base_url()}/currencies",
                headers=_headers(),
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("currencies", [])
                return []
    except Exception as e:
        logger.error(f"NowPayments get_currencies exception: {e}")
        return []


async def get_estimated_price(amount: float, currency_from: str, currency_to: str) -> Optional[float]:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{_base_url()}/estimate",
                headers=_headers(),
                params={"amount": amount, "currency_from": "usd", "currency_to": currency_to.lower()},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return float(data.get("estimated_amount", 0))
                return None
    except Exception as e:
        logger.error(f"NowPayments get_estimate exception: {e}")
        return None


def verify_ipn_signature(request_body: bytes, received_sig: str) -> bool:
    ipn_secret = ""  # set if using webhook
    if not ipn_secret:
        return True
    expected = hmac.new(
        ipn_secret.encode(), request_body, hashlib.sha512
    ).hexdigest()
    return hmac.compare_digest(expected, received_sig)


FINISHED_STATUSES = {"finished", "confirmed"}
FAILED_STATUSES   = {"failed", "refunded", "expired"}
