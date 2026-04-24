from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class User:
    user_id: int
    username: str
    balance: float
    referral_id: Optional[int]
    referral_earnings: float
    total_wagered: float
    join_date: str
    bonus_eligible: int


@dataclass
class Transaction:
    id: int
    user_id: int
    type: str
    amount: float
    status: str
    date: str


@dataclass
class Withdrawal:
    id: int
    user_id: int
    amount: float
    upi_id: str
    status: str
    date: str


@dataclass
class Deposit:
    id: int
    user_id: int
    method: str
    amount: float
    txn_id: str
    status: str
    date: str
    
