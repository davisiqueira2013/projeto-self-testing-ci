"""Utilitários compartilhados pelos testes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import ClassVar

from wallet.domain.models import Account
from wallet.gateways.kyc import KycResult


def make_cpf(seed: int) -> str:
    """Gera um CPF válido e determinístico a partir de uma semente."""
    base = f"{(seed * 7919 + 123_456_789) % 1_000_000_000:09d}"

    def digit(digits: str) -> str:
        weight = len(digits) + 1
        total = sum(int(d) * (weight - i) for i, d in enumerate(digits))
        rest = (total * 10) % 11
        return "0" if rest == 10 else str(rest)

    first = digit(base)
    return base + first + digit(base + first)


def make_account(balance: int = 1_000, currency: str = "BRL", account_id: str = "acc-1") -> Account:
    return Account(account_id, "Ana", "52998224725", currency, balance, datetime.now(UTC))


class StubKycProvider:
    """STUB: devolve sempre o mesmo veredito cadastral, sem lógica e sem I/O."""

    def __init__(self, approved: bool = True, reason: str = "") -> None:
        self._result = KycResult(approved, reason)

    def validate(self, holder_name: str, document: str) -> KycResult:
        return self._result


class StubExchangeRateProvider:
    """STUB: taxas de câmbio fixas para tornar as conversões previsíveis."""

    RATES: ClassVar[dict[tuple[str, str], Decimal]] = {
        ("USD", "BRL"): Decimal("5.00"),
        ("BRL", "USD"): Decimal("0.20"),
    }

    def get_rate(self, source: str, target: str) -> Decimal:
        if source == target:
            return Decimal("1")
        return self.RATES[(source, target)]


class FixedClock:
    """Relógio controlável para testes de extrato por período."""

    def __init__(self, start: datetime | None = None) -> None:
        self.now = start or datetime(2026, 11, 10, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: float) -> None:
        self.now += timedelta(**delta)
