"""Regras financeiras puras (sem I/O). Desenvolvidas via TDD."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from typing import TYPE_CHECKING

from wallet.domain.errors import (
    InsufficientFundsError,
    InvalidAmountError,
    SameAccountTransferError,
    UnsupportedCurrencyError,
)

if TYPE_CHECKING:  # pragma: no cover
    from wallet.domain.models import Account, Transaction

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


def plan_transfer(
    source: Account, target: Account, amount_cents: int, rate: Decimal
) -> tuple[int, int]:
    """Calcula (valor debitado, valor creditado) sem alterar as contas."""
    if source.id == target.id:
        raise SameAccountTransferError("source and target accounts must differ")
    debit = validate_amount(amount_cents)
    if not source.can_debit(debit):
        raise InsufficientFundsError(source.id, source.balance_cents, debit)
    credit = debit if source.currency == target.currency else convert(debit, rate)
    return debit, credit


@dataclass(frozen=True)
class StatementSummary:
    total_credits_cents: int
    total_debits_cents: int
    count: int

    @property
    def net_cents(self) -> int:
        return self.total_credits_cents - self.total_debits_cents


def summarize(transactions: Iterable[Transaction]) -> StatementSummary:
    credits = debits = count = 0
    for tx in transactions:
        count += 1
        if tx.type == "CREDIT":
            credits += tx.amount_cents
        else:
            debits += tx.amount_cents
    return StatementSummary(credits, debits, count)


_NON_DIGITS = re.compile(r"\D")


def normalize_document(document: str) -> str:
    return _NON_DIGITS.sub("", document or "")


def _cpf_check_digit(digits: str) -> int:
    weight = len(digits) + 1
    total = sum(int(d) * (weight - i) for i, d in enumerate(digits))
    remainder = (total * 10) % 11
    return 0 if remainder == 10 else remainder


def is_valid_cpf(document: str) -> bool:
    cpf = normalize_document(document)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    first = _cpf_check_digit(cpf[:9])
    second = _cpf_check_digit(cpf[:9] + str(first))
    return cpf[9:] == f"{first}{second}"
