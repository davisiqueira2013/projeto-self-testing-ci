"""Regras financeiras puras (sem I/O). Desenvolvidas via TDD."""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal

from wallet.domain.errors import InvalidAmountError, UnsupportedCurrencyError

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
