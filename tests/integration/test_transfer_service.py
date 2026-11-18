import logging
import threading
from unittest.mock import ANY

import httpx
import pytest

from wallet.domain.errors import (
    AccountNotFoundError,
    InsufficientFundsError,
    InvalidRequestError,
    SameAccountTransferError,
)
from wallet.domain.models import TransactionType


def test_transfer_moves_balance_and_records_both_entries(transfers, repo, open_account, clock):
    source, target = open_account(10_000), open_account(0)

    result, replayed = transfers.transfer(source.id, target.id, 2_500, "key-1")

    assert replayed is False
    assert repo.get_account(source.id).balance_cents == 7_500
    assert repo.get_account(target.id).balance_cents == 2_500
    debit = repo.list_transactions(source.id, tx_type=TransactionType.DEBIT)
    credit = repo.list_transactions(target.id, tx_type=TransactionType.CREDIT)
    assert [(t.amount_cents, t.balance_after_cents, t.counterparty_account_id) for t in debit] == [
        (2_500, 7_500, target.id)
    ]
    assert [(t.amount_cents, t.transfer_id) for t in credit] == [(2_500, result.transfer_id)]
    assert result.created_at == clock.now.isoformat()


# ---------------------------------------------------------------- MOCK -----
def test_antifraud_mock_receives_exactly_one_call_with_expected_payload(
    transfers, open_account, antifraud_mock
):
    source, target = open_account(10_000), open_account(0)

    result, _ = transfers.transfer(source.id, target.id, 1_000, "key-1")

    antifraud_mock.notify_transfer.assert_called_once_with(
        {
            "event": "transfer.completed",
            "transfer_id": result.transfer_id,
            "source_account_id": source.id,
            "target_account_id": target.id,
            "amount_cents": 1_000,
            "currency": "BRL",
            "high_risk": False,
            "occurred_at": ANY,
        }
    )


def test_antifraud_mock_flags_high_risk_transfer(transfers, open_account, antifraud_mock):
    source, target = open_account(100_000), open_account(0)

    transfers.transfer(source.id, target.id, 50_000, "key-1")  # limiar = 50_000

    (event,), _ = antifraud_mock.notify_transfer.call_args
    assert event["high_risk"] is True
    assert event["amount_cents"] == 50_000


def test_antifraud_mock_is_not_called_when_transfer_fails(transfers, open_account, antifraud_mock):
    source, target = open_account(100), open_account(0)

    with pytest.raises(InsufficientFundsError):
        transfers.transfer(source.id, target.id, 101, "key-1")

    antifraud_mock.notify_transfer.assert_not_called()


def test_antifraud_call_count_matches_number_of_effective_transfers(
    transfers, open_account, antifraud_mock
):
    source, target = open_account(10_000), open_account(0)
    for i in range(3):
        transfers.transfer(source.id, target.id, 100, f"key-{i}")
    transfers.transfer(source.id, target.id, 100, "key-0")  # replay: não notifica de novo

    assert antifraud_mock.notify_transfer.call_count == 3


def test_antifraud_failure_does_not_roll_back_committed_transfer(
    transfers, repo, open_account, antifraud_mock, caplog
):
    antifraud_mock.notify_transfer.side_effect = httpx.ConnectError("webhook down")
    source, target = open_account(1_000), open_account(0)

    with caplog.at_level(logging.WARNING):
        result, _ = transfers.transfer(source.id, target.id, 400, "key-1")

    assert repo.get_account(target.id).balance_cents == 400
    assert antifraud_mock.notify_transfer.call_count == 1
    assert f"antifraud notification failed for transfer {result.transfer_id}" in caplog.text


# ---------------------------------------------------------------- STUB -----
def test_cross_currency_transfer_uses_stubbed_exchange_rate(transfers, repo, open_account):
    source, target = open_account(10_000, "USD"), open_account(0, "BRL")

    result, _ = transfers.transfer(source.id, target.id, 1_000, "key-1")

    # STUB de câmbio fixa USD->BRL = 5.00
    assert (result.amount_cents, result.credited_cents, result.exchange_rate) == (
        1_000,
        5_000,
        "5.00",
    )
    assert repo.get_account(target.id).balance_cents == 5_000


# --------------------------------------------------------- idempotência ----
def test_same_idempotency_key_returns_original_result_without_new_debit(
    transfers, repo, open_account
):
    source, target = open_account(10_000), open_account(0)

    first, replayed_first = transfers.transfer(source.id, target.id, 1_000, "key-1")
    second, replayed_second = transfers.transfer(source.id, target.id, 1_000, "key-1")

    assert (replayed_first, replayed_second) == (False, True)
    assert second == first
    assert repo.get_account(source.id).balance_cents == 9_000
    assert len(repo.list_transactions(source.id, tx_type=TransactionType.DEBIT)) == 1


@pytest.mark.parametrize("key", ["", "   ", "x" * 129])
def test_invalid_idempotency_key(transfers, open_account, key):
    source, target = open_account(100), open_account(0)
    with pytest.raises(InvalidRequestError):
        transfers.transfer(source.id, target.id, 10, key)


# ------------------------------------------------------------ erros --------
def test_unknown_accounts(transfers, open_account):
    account = open_account(100)
    with pytest.raises(AccountNotFoundError):
        transfers.transfer("missing", account.id, 10, "k1")
    with pytest.raises(AccountNotFoundError):
        transfers.transfer(account.id, "missing", 10, "k2")


def test_failed_transfer_rolls_back_and_frees_idempotency_key(transfers, repo, open_account):
    source = open_account(100)
    with pytest.raises(SameAccountTransferError):
        transfers.transfer(source.id, source.id, 10, "key-1")
    assert repo.get_idempotency("key-1") is None
    assert repo.get_account(source.id).balance_cents == 100


# ----------------------------------------------------------- concorrência --
def test_concurrent_transfers_never_overdraw_and_conserve_money(transfers, repo, open_account):
    source, target = open_account(30), open_account(0)
    outcomes: list[str] = []
    barrier = threading.Barrier(50)

    def worker(i: int) -> None:
        barrier.wait()
        try:
            transfers.transfer(source.id, target.id, 1, f"concurrent-{i}")
            outcomes.append("ok")
        except InsufficientFundsError:
            outcomes.append("insufficient")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert outcomes.count("ok") == 30
    assert outcomes.count("insufficient") == 20
    assert repo.get_account(source.id).balance_cents == 0
    assert repo.get_account(target.id).balance_cents == 30
