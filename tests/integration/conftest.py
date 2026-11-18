import pytest

from wallet.repositories.sqlite import SqliteWalletRepository


@pytest.fixture
def repo():
    """Banco SQLite **em memória**, isolado por teste."""
    repository = SqliteWalletRepository(":memory:")
    yield repository
    repository.close()
