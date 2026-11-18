from unittest.mock import Mock

import pytest
from wallet.services.statement_service import StatementService

from tests.support import FixedClock, StubExchangeRateProvider, StubKycProvider, make_cpf
from wallet.gateways.antifraud import AntiFraudGateway
from wallet.repositories.sqlite import SqliteWalletRepository
from wallet.services.account_service import AccountService
from wallet.services.transfer_service import TransferService


@pytest.fixture
def repo():
    """Banco SQLite **em memória**, isolado por teste."""
    repository = SqliteWalletRepository(":memory:")
    yield repository
    repository.close()


@pytest.fixture
def clock():
    return FixedClock()


@pytest.fixture
def antifraud_mock():
    """MOCK: usado para verificar chamadas, contagem e parâmetros enviados ao anti-fraude."""
    return Mock(spec=AntiFraudGateway)


@pytest.fixture
def accounts(repo, clock):
    return AccountService(repo, StubKycProvider(approved=True), clock=clock)


@pytest.fixture
def transfers(repo, antifraud_mock, clock):
    return TransferService(
        repo,
        antifraud_mock,
        StubExchangeRateProvider(),
        high_risk_threshold_cents=50_000,
        clock=clock,
    )


@pytest.fixture
def statements(repo):
    return StatementService(repo)


@pytest.fixture
def open_account(accounts):
    counter = iter(range(1, 10_000))

    def _open(balance: int = 0, currency: str = "BRL", name: str = "Titular Teste"):
        return accounts.open_account(name, make_cpf(next(counter)), currency, balance)

    return _open
