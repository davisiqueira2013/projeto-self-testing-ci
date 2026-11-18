import sqlite3
from datetime import UTC, datetime

import pytest

from tests.support import make_account


class TestSqliteRepository:
    def test_atomic_rolls_back_everything_on_error(self, repo):
        def failing_unit_of_work():
            with repo.atomic():
                repo.add_account(make_account(100, account_id="a"))
                raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            failing_unit_of_work()
        assert repo.get_account("a") is None

    def test_nested_atomic_commits_once_at_outermost_level(self, repo):
        with repo.atomic(), repo.atomic():
            repo.add_account(make_account(100, account_id="a"))
        assert repo.get_account("a").balance_cents == 100

    def test_database_rejects_negative_balance(self, repo):
        account = make_account(100, account_id="a")
        repo.add_account(account)
        account.balance_cents = -1
        with pytest.raises(sqlite3.IntegrityError):
            repo.save_balance(account)

    def test_idempotency_record_roundtrip(self, repo):
        repo.save_idempotency("k", "hash", {"x": 1}, datetime.now(UTC))
        record = repo.get_idempotency("k")
        assert (record.key, record.request_hash, record.response) == ("k", "hash", {"x": 1})

    def test_file_database_uses_wal(self, tmp_path):
        from wallet.repositories.sqlite import SqliteWalletRepository

        file_repo = SqliteWalletRepository(str(tmp_path / "wallet.db"))
        file_repo.add_account(make_account(1, account_id="a"))
        assert file_repo.get_account("a") is not None
        file_repo.close()
