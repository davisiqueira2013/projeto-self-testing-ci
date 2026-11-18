from datetime import date

import pytest

from wallet.domain.errors import AccountNotFoundError, InvalidRequestError
from wallet.domain.models import TransactionType


@pytest.fixture
def history(transfers, open_account, clock):
    """Conta com movimentações em 10/11 (saldo inicial), 11/11 e 12/11 (23:59)."""
    alice = open_account(10_000)  # 2026-11-10 12:00 crédito inicial
    bob = open_account(10_000)
    clock.advance(days=1)  # 2026-11-11 12:00
    transfers.transfer(alice.id, bob.id, 1_000, "k1")
    clock.advance(days=1, hours=11, minutes=59)  # 2026-11-12 23:59
    transfers.transfer(bob.id, alice.id, 300, "k2")
    return alice


def test_full_statement_is_ordered_and_summarized(statements, history):
    st = statements.get_statement(history.id)
    assert [(t.type, t.amount_cents) for t in st.transactions] == [
        (TransactionType.CREDIT, 10_000),
        (TransactionType.DEBIT, 1_000),
        (TransactionType.CREDIT, 300),
    ]
    assert st.summary.net_cents == 9_300
    assert st.account.balance_cents == 9_300


def test_filter_by_type(statements, history):
    st = statements.get_statement(history.id, tx_type=TransactionType.DEBIT)
    assert [t.amount_cents for t in st.transactions] == [1_000]
    assert st.summary.total_credits_cents == 0


def test_filter_by_start_date(statements, history):
    st = statements.get_statement(history.id, start_date=date(2026, 11, 11))
    assert [t.amount_cents for t in st.transactions] == [1_000, 300]


def test_inverted_period_is_rejected(statements, history):
    with pytest.raises(InvalidRequestError):
        statements.get_statement(
            history.id, start_date=date(2026, 11, 12), end_date=date(2026, 11, 11)
        )


def test_unknown_account(statements):
    with pytest.raises(AccountNotFoundError):
        statements.get_statement("missing")
