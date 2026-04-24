"""
Oxapay.com crypto payment - White Label API (returns wallet address directly)
Docs: https://docs.oxapay.com
"""
import aiohttp
import hashlib
import hmac
from typing import Optional, Dict
from utils.logger import logger

_MERCHANT_KEY = "ZVPRPD-BQAIMR-HTQE1F-CG1HUY"
_BASE_URL = "https://api.oxapay.com"

def _headers() -> dict:
    return {
        "merchant_api_key": _MERCHANT_KEY,
        "Content-Type": "application/json",
    }

# White-label API returns actual wallet address (not payLink)
async def create_invoice(amount_usd: float, currency: str, network: str,
                          order_id: str, description: str) -> Optional[Dict]:
    """
    White-label payment — returns pay_address, pay_amount, track_id directly.
    """
    payload = {
        "amount": round(amount_usd, 2),
        "currency": "USD",
        "pay_currency": currency,
        "network": network,
        "lifetime": 60,
        "fee_paid_by_payer": 0,
        "under_paid_coverage": 2.5,
        "order_id": order_id,
        "description": description,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{_BASE_URL}/v1/payment/white-label",
                headers=_headers(),
                json=payload,
                timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                data = await resp.json()
                logger.info(f"Oxapay white-label [{resp.status}]: {data}")
                # White-label returns data directly in response
                if resp.status == 200 and data.get("data"):
                    return data["data"]
                # Try legacy endpoint if new one fails
                logger.warning(f"White-label failed, trying legacy: {data}")
                return await _create_invoice_legacy(amount_usd, currency, network, order_id, description)
    except Exception as e:
        logger.error(f"Oxapay create_invoice exception: {e}")
        return await _create_invoice_legacy(amount_usd, currency, network, order_id, description)


async def _create_invoice_legacy(amount_usd: float, currency: str, network: str,
                                   order_id: str, description: str) -> Optional[Dict]:
    """Legacy API — returns payLink. We extract address from payment info."""
    payload = {
        "merchant": _MERCHANT_KEY,
        "amount": round(amount_usd, 2),
        "currency": "USD",
        "payCurrency": currency,
        "network": network,
        "orderId": order_id,
        "description": description,
        "feePaidByPayer": 0,
        "underPaidCover": 2.5,
        "lifeTime": 60,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{_BASE_URL}/merchants/request",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                data = await resp.json()
                logger.info(f"Oxapay legacy [{resp.status}]: {data}")
                if data.get("result") == 100:
                    track_id = str(data.get("trackId", ""))
                    pay_link = data.get("payLink", "")
                    # Get actual address from payment info
                    address = await _get_payment_address(track_id)
                    return {
                        "track_id": track_id,
                        "pay_address": address,
                        "pay_link": pay_link,
                        "pay_amount": data.get("amount", amount_usd),
                        "pay_currency": currency,
                        "network": network,
                        "expired_at": data.get("expiredAt", ""),
                    }
                return None
    except Exception as e:
        logger.error(f"Oxapay legacy exception: {e}")
        return None


async def _get_payment_address(track_id: str) -> str:
    """Get wallet address for a payment by track_id."""
    try:
        async with aiohttp.ClientSession() as session:
            # New API
            async with session.get(
                f"{_BASE_URL}/v1/payment/{track_id}",
                headers=_headers(),
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                data = await resp.json()
                logger.info(f"Oxapay payment info [{resp.status}]: {data}")
                if resp.status == 200:
                    d = data.get("data", data)
                    return d.get("pay_address") or d.get("payAddress") or d.get("address") or ""
    except Exception as e:
        logger.error(f"Oxapay get address exception: {e}")
    return ""


async def check_payment(track_id: str) -> Optional[Dict]:
    """Check payment status."""
    try:
        # Try new API first
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{_BASE_URL}/v1/payment/{track_id}",
                headers=_headers(),
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                data = await resp.json()
                if resp.status == 200:
                    return data.get("data", data)
    except Exception:
        pass
    # Try legacy
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{_BASE_URL}/merchants/inquiry",
                json={"merchant": _MERCHANT_KEY, "trackId": track_id},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                data = await resp.json()
                if data.get("result") == 100:
                    return data
                return None
    except Exception as e:
        logger.error(f"Oxapay check_payment exception: {e}")
        return None


PAID_STATUSES   = {"Paid", "paid", "confirmed", "Confirmed"}
FAILED_STATUSES = {"Expired", "expired", "Error", "error", "Failed", "failed"}
