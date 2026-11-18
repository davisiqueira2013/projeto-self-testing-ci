"""Provedor de câmbio."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from wallet.domain.errors import UnsupportedCurrencyError

_PRECISION = Decimal("0.000001")


class ExchangeRateProvider(Protocol):
    def get_rate(self, source: str, target: str) -> Decimal: ...


class StaticExchangeRateProvider:
    """Taxas fixas configuradas em relação ao BRL (ex.: USD=5.40)."""

    def __init__(self, rates_to_brl: dict[str, Decimal]):
        self._rates = {"BRL": Decimal("1"), **{k.upper(): v for k, v in rates_to_brl.items()}}

    def get_rate(self, source: str, target: str) -> Decimal:
        if source == target:
            return Decimal("1")
        try:
            return (self._rates[source] / self._rates[target]).quantize(_PRECISION)
        except KeyError as exc:
            raise UnsupportedCurrencyError(f"no exchange rate for {exc.args[0]}") from exc
