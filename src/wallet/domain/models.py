"""Entidades do domínio."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum

from wallet.domain.errors import InsufficientFundsError
from wallet.domain.rules import validate_amount


class TransactionType(StrEnum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


@dataclass
class Account:
    id: str
    holder_name: str
    document: str
    currency: str
    balance_cents: int
    created_at: datetime

    def can_debit(self, amount_cents: int) -> bool:
        return amount_cents <= self.balance_cents

    def debit(self, amount_cents: int) -> None:
        validate_amount(amount_cents, maximum=None)
        if not self.can_debit(amount_cents):
            raise InsufficientFundsError(self.id, self.balance_cents, amount_cents)
        self.balance_cents -= amount_cents

    def credit(self, amount_cents: int) -> None:
        validate_amount(amount_cents, maximum=None)
        self.balance_cents += amount_cents


@dataclass(frozen=True)
class Transaction:
    id: str
    account_id: str
    type: TransactionType
    amount_cents: int
    balance_after_cents: int
    created_at: datetime
    transfer_id: str | None = None
    counterparty_account_id: str | None = None
    description: str = ""


@dataclass(frozen=True)
class TransferResult:
    transfer_id: str
    source_account_id: str
    target_account_id: str
    amount_cents: int
    credited_cents: int
    source_currency: str
    target_currency: str
    exchange_rate: str
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> TransferResult:
        return cls(**data)
