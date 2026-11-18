import json
import sqlite3
from datetime import UTC, datetime

import httpx
import pytest
from wallet.container import build_container

from tests.support import make_account
from wallet.config import Settings
from wallet.gateways.antifraud import NullAntiFraudGateway, WebhookAntiFraudGateway


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


class TestWebhookAntiFraudGateway:
    def test_posts_event_as_json_to_configured_url(self):
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(202)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        gateway = WebhookAntiFraudGateway("https://fraud.example/hook", client=client)

        gateway.notify_transfer({"event": "transfer.completed", "amount_cents": 10})

        [request] = captured
        assert request.method == "POST"
        assert str(request.url) == "https://fraud.example/hook"
        assert request.headers["X-Event-Type"] == "transfer.completed"
        assert json.loads(request.content) == {"event": "transfer.completed", "amount_cents": 10}

    def test_raises_on_server_error(self):
        client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
        gateway = WebhookAntiFraudGateway("https://fraud.example/hook", client=client)
        with pytest.raises(httpx.HTTPStatusError):
            gateway.notify_transfer({"amount_cents": 10})

    def test_null_gateway_does_nothing(self):
        assert NullAntiFraudGateway().notify_transfer({"any": "event"}) is None


class TestContainer:
    def test_uses_webhook_gateway_when_url_is_configured(self):
        container = build_container(Settings(antifraud_webhook_url="https://fraud.example/hook"))
        assert isinstance(container.transfers._antifraud, WebhookAntiFraudGateway)
        container.repository.close()

    def test_uses_null_gateway_by_default(self):
        container = build_container(Settings())
        assert isinstance(container.transfers._antifraud, NullAntiFraudGateway)
        container.repository.close()
