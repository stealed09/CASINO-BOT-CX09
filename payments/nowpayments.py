"""
NowPayments.io integration for automated crypto deposits.
Documentation: https://documenter.getpostman.com/view/7907941/2s93JqTRst
"""
import aiohttp
import hashlib
import hmac
import json
from typing import Optional, Dict
from config import NOWPAYMENTS_API_KEY, NOWPAYMENTS_API_URL, NOWPAYMENTS_IPN_SECRET
from utils.logger import logger


HEADERS = {
    "x-api-key": NOWPAYMENTS_API_KEY,
    "Content-Type": "application/json",
}


async def create_payment(pay_currency: str, price_amount: float,
                          order_id: str, order_description: str) -> Optional[Dict]:
    """
    Create a new crypto payment invoice via NowPayments.
    Returns payment details including address and pay_amount.
    """
    payload = {
        "price_amount": price_amount,
        "price_currency": "usd",   # tokens are priced in USD equivalent
        "pay_currency": pay_currency.lower(),
        "order_id": order_id,
        "order_description": order_description,
        "ipn_callback_url": "",    # Optional: set if you have a public webhook endpoint
        "is_fixed_rate": False,
        "is_fee_paid_by_user": False,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{NOWPAYMENTS_API_URL}/payment",
                headers=HEADERS,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json()
                if resp.status == 201:
                    return data
                logger.error(f"NowPayments create_payment error {resp.status}: {data}")
                return None
    except Exception as e:
        logger.error(f"NowPayments create_payment exception: {e}")
        return None


async def get_payment_status(payment_id: str) -> Optional[Dict]:
    """Get current status of a payment."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{NOWPAYMENTS_API_URL}/payment/{payment_id}",
                headers=HEADERS,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
    except Exception as e:
        logger.error(f"NowPayments get_status exception: {e}")
        return None


async def get_available_currencies() -> list:
    """Get list of currencies supported by NowPayments."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{NOWPAYMENTS_API_URL}/currencies",
                headers=HEADERS,
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
    """Get estimated amount in pay_currency for given price."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{NOWPAYMENTS_API_URL}/estimate",
                headers=HEADERS,
                params={
                    "amount": amount,
                    "currency_from": "usd",
                    "currency_to": currency_to.lower(),
                },
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
    """
    Verify the HMAC-SHA512 IPN callback signature from NowPayments.
    Use this in your webhook endpoint.
    """
    if not NOWPAYMENTS_IPN_SECRET:
        return True  # skip if not configured
    expected = hmac.new(
        NOWPAYMENTS_IPN_SECRET.encode(),
        request_body,
        hashlib.sha512
    ).hexdigest()
    return hmac.compare_digest(expected, received_sig)


# Payment status meanings from NowPayments:
# waiting      - payment created, waiting for funds
# confirming   - transaction found, waiting for confirmations
# confirmed    - confirmed on blockchain
# sending      - NowPayments is forwarding funds
# partially_paid - only partial amount received (treat as pending)
# finished     - all done, credit user
# failed       - payment failed
# refunded     - refunded
# expired      - payment expired

FINISHED_STATUSES = {"finished", "confirmed"}
FAILED_STATUSES = {"failed", "refunded", "expired"}
