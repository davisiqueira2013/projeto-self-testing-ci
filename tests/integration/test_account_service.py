import pytest

from tests.support import StubKycProvider, make_cpf
from wallet.domain.errors import (
    AccountNotFoundError,
    DuplicateAccountError,
    InvalidAmountError,
    InvalidHolderError,
    UnsupportedCurrencyError,
)
from wallet.domain.models import TransactionType
from wallet.services.account_service import AccountService


def test_open_account_with_initial_balance_persists_account_and_credit(accounts, repo, clock):
    account = accounts.open_account(" Ana Souza ", "529.982.247-25", "brl", 10_000)

    stored = repo.get_account(account.id)
    assert stored.holder_name == "Ana Souza"
    assert stored.document == "52998224725"
    assert stored.currency == "BRL"
    assert stored.balance_cents == 10_000
    assert stored.created_at == clock.now

    [tx] = repo.list_transactions(account.id)
    assert tx.type is TransactionType.CREDIT
    assert (tx.amount_cents, tx.balance_after_cents, tx.description) == (
        10_000,
        10_000,
        "Saldo inicial",
    )


def test_open_account_without_initial_balance_creates_no_transaction(accounts, repo):
    account = accounts.open_account("Ana Souza", make_cpf(1))
    assert repo.get_account(account.id).balance_cents == 0
    assert repo.list_transactions(account.id) == []


def test_rejected_kyc_from_stub_prevents_account_creation(repo):
    # STUB fornece o dado cadastral "reprovado" sem depender de serviço real.
    service = AccountService(repo, StubKycProvider(approved=False, reason="CPF irregular"))
    with pytest.raises(InvalidHolderError, match="CPF irregular"):
        service.open_account("Ana Souza", make_cpf(1), "BRL", 500)


def test_rejected_kyc_without_reason_uses_default_message(repo):
    service = AccountService(repo, StubKycProvider(approved=False))
    with pytest.raises(InvalidHolderError, match="rejected by KYC"):
        service.open_account("Ana Souza", make_cpf(1))


def test_duplicate_document_is_rejected_and_nothing_extra_is_persisted(accounts, repo):
    accounts.open_account("Ana Souza", make_cpf(7), "BRL", 100)
    with pytest.raises(DuplicateAccountError):
        accounts.open_account("Outra Pessoa", make_cpf(7), "BRL", 999)


@pytest.mark.parametrize("initial", [-1, 1.5, True])
def test_invalid_initial_balance(accounts, initial):
    with pytest.raises(InvalidAmountError):
        accounts.open_account("Ana Souza", make_cpf(1), "BRL", initial)


def test_unsupported_currency(accounts):
    with pytest.raises(UnsupportedCurrencyError):
        accounts.open_account("Ana Souza", make_cpf(1), "JPY")


def test_get_account(accounts, open_account):
    created = open_account(50)
    assert accounts.get_account(created.id) == created


def test_get_missing_account(accounts):
    with pytest.raises(AccountNotFoundError):
        accounts.get_account("nope")
