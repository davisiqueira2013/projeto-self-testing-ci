"""Utilitários compartilhados pelos testes."""

from __future__ import annotations

from datetime import UTC, datetime

from wallet.domain.models import Account


def make_account(balance: int = 1_000, currency: str = "BRL", account_id: str = "acc-1") -> Account:
    return Account(account_id, "Ana", "52998224725", currency, balance, datetime.now(UTC))
