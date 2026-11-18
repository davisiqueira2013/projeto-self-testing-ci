"""Regras financeiras puras (sem I/O). Desenvolvidas via TDD."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

from wallet.domain.errors import (
    InsufficientFundsError,
    InvalidAmountError,
    SameAccountTransferError,
    UnsupportedCurrencyError,
)

MAX_TRANSFER_CENTS = 100_000_000  # R$ 1.000.000,00 por operação
SUPPORTED_CURRENCIES = frozenset({"BRL", "USD", "EUR"})
_CENT = Decimal("1")


def validate_amount(amount_cents: object, *, maximum: int | None = MAX_TRANSFER_CENTS) -> int:
    """Valida um valor monetário em centavos (inteiro, positivo e dentro do limite)."""
    if isinstance(amount_cents, bool) or not isinstance(amount_cents, int):
        raise InvalidAmountError("amount must be an integer number of cents")
    if amount_cents <= 0:
        raise InvalidAmountError("amount must be positive")
    if maximum is not None and amount_cents > maximum:
        raise InvalidAmountError(f"amount exceeds the limit of {maximum} cents")
    return amount_cents


def validate_currency(currency: str) -> str:
    code = (currency or "").strip().upper()
    if code not in SUPPORTED_CURRENCIES:
        raise UnsupportedCurrencyError(f"currency {currency!r} is not supported")
    return code


def convert(amount_cents: int, rate: Decimal) -> int:
    """Converte centavos usando arredondamento bancário (HALF_EVEN)."""
    if rate <= 0:
        raise InvalidAmountError("exchange rate must be positive")
    converted = (Decimal(amount_cents) * rate).quantize(_CENT, rounding=ROUND_HALF_EVEN)
    if converted <= 0:
        raise InvalidAmountError("converted amount rounds to zero")
    return int(converted)


def is_high_risk(amount_cents: int, threshold_cents: int) -> bool:
    return amount_cents >= threshold_cents


def plan_transfer(source, target, amount_cents, rate):
    if source.id == target.id:
        raise SameAccountTransferError("source and target accounts must differ")
    debit = validate_amount(amount_cents)
    if source.balance_cents < debit:
        raise InsufficientFundsError(source.id, source.balance_cents, debit)
    if source.currency == target.currency:
        credit = debit
    else:
        credit = convert(debit, rate)
    return debit, credit


@dataclass(frozen=True)
class StatementSummary:
    total_credits_cents: int
    total_debits_cents: int
    count: int

    @property
    def net_cents(self) -> int:
        return self.total_credits_cents - self.total_debits_cents


def summarize(transactions):
    transactions = list(transactions)
    credits = sum(t.amount_cents for t in transactions if t.type == "CREDIT")
    debits = sum(t.amount_cents for t in transactions if t.type == "DEBIT")
    return StatementSummary(credits, debits, len(transactions))
