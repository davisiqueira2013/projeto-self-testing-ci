from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, StrictInt


class AccountIn(BaseModel):
    holder_name: str = Field(min_length=1, max_length=120)
    document: str = Field(min_length=11, max_length=14)
    currency: str = Field(default="BRL", min_length=3, max_length=3)
    initial_balance_cents: StrictInt = Field(default=0, ge=0)


class AccountOut(BaseModel):
    id: str
    holder_name: str
    document: str
    currency: str
    balance_cents: int
    created_at: datetime


class TransferIn(BaseModel):
    source_account_id: str = Field(min_length=1)
    target_account_id: str = Field(min_length=1)
    amount_cents: StrictInt


class TransferOut(BaseModel):
    transfer_id: str
    source_account_id: str
    target_account_id: str
    amount_cents: int
    credited_cents: int
    source_currency: str
    target_currency: str
    exchange_rate: str
    created_at: datetime


class TransactionOut(BaseModel):
    id: str
    type: str
    amount_cents: int
    balance_after_cents: int
    created_at: datetime
    transfer_id: str | None
    counterparty_account_id: str | None
    description: str


class SummaryOut(BaseModel):
    total_credits_cents: int
    total_debits_cents: int
    net_cents: int
    count: int


class StatementOut(BaseModel):
    account_id: str
    currency: str
    balance_cents: int
    start_date: date | None
    end_date: date | None
    type: str | None
    summary: SummaryOut
    transactions: list[TransactionOut]


class ErrorOut(BaseModel):
    error: str
    message: str
