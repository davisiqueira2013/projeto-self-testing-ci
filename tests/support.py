"""Utilitários compartilhados pelos testes."""

from __future__ import annotations

from datetime import UTC, datetime

from wallet.domain.models import Account


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
