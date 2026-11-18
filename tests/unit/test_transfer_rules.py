from datetime import UTC, datetime
from decimal import Decimal

import pytest
from wallet.domain.models import Transaction, TransactionType

from tests.support import make_account
from wallet.domain.errors import (
    InsufficientFundsError,
    InvalidAmountError,
    SameAccountTransferError,
)
from wallet.domain.rules import plan_transfer, summarize


class TestPlanTransfer:
    def test_same_currency_debits_and_credits_same_amount(self):
        source, target = make_account(1_000, account_id="a"), make_account(0, account_id="b")
        assert plan_transfer(source, target, 400, Decimal("1")) == (400, 400)

    def test_does_not_mutate_accounts(self):
        source, target = make_account(1_000, account_id="a"), make_account(0, account_id="b")
        plan_transfer(source, target, 400, Decimal("1"))
        assert (source.balance_cents, target.balance_cents) == (1_000, 0)

    def test_cross_currency_converts_credited_amount(self):
        source = make_account(10_000, "USD", "a")
        target = make_account(0, "BRL", "b")
        assert plan_transfer(source, target, 1_000, Decimal("5.40")) == (1_000, 5_400)

    def test_rejects_transfer_to_same_account(self):
        account = make_account(1_000, account_id="a")
        with pytest.raises(SameAccountTransferError):
            plan_transfer(account, account, 10, Decimal("1"))

    def test_rejects_insufficient_funds(self):
        source, target = make_account(99, account_id="a"), make_account(0, account_id="b")
        with pytest.raises(InsufficientFundsError):
            plan_transfer(source, target, 100, Decimal("1"))

    def test_rejects_invalid_amount_before_checking_funds(self):
        source, target = make_account(0, account_id="a"), make_account(0, account_id="b")
        with pytest.raises(InvalidAmountError):
            plan_transfer(source, target, -10, Decimal("1"))


def _tx(tx_type: TransactionType, amount: int) -> Transaction:
    return Transaction("t", "a", tx_type, amount, 0, datetime.now(UTC))


class TestSummarize:
    def test_empty_statement(self):
        summary = summarize([])
        assert (summary.total_credits_cents, summary.total_debits_cents, summary.count) == (0, 0, 0)
        assert summary.net_cents == 0

    def test_sums_credits_and_debits_separately(self):
        summary = summarize(
            [
                _tx(TransactionType.CREDIT, 1_000),
                _tx(TransactionType.DEBIT, 300),
                _tx(TransactionType.DEBIT, 200),
            ]
        )
        assert summary.total_credits_cents == 1_000
        assert summary.total_debits_cents == 500
        assert summary.net_cents == 500
        assert summary.count == 3
