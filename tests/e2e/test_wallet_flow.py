"""Testes ponta a ponta: requisições HTTP reais contra a aplicação ASGI completa."""

from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from wallet.container import build_container
from wallet.controllers.api import create_app

from tests.support import make_cpf
from wallet.config import Settings
from wallet.gateways.antifraud import AntiFraudGateway


@pytest.fixture
def antifraud():
    return Mock(spec=AntiFraudGateway)


@pytest.fixture
def client(antifraud):
    container = build_container(Settings(), antifraud=antifraud)
    with TestClient(create_app(container)) as http:
        yield http
    container.repository.close()


def create_account(client, seed, balance=0, currency="BRL", name="Cliente E2E"):
    response = client.post(
        "/accounts",
        json={
            "holder_name": name,
            "document": make_cpf(seed),
            "currency": currency,
            "initial_balance_cents": balance,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_register_transfer_and_statement_full_flow(client, antifraud):
    alice = create_account(client, 1, balance=50_000, name="Alice Lima")
    bob = create_account(client, 2, name="Bob Costa")

    transfer = client.post(
        "/transfers",
        json={
            "source_account_id": alice["id"],
            "target_account_id": bob["id"],
            "amount_cents": 12_345,
        },
        headers={"Idempotency-Key": "e2e-001"},
    )
    assert transfer.status_code == 201
    body = transfer.json()
    assert (body["amount_cents"], body["credited_cents"]) == (12_345, 12_345)

    replay = client.post(
        "/transfers",
        json={
            "source_account_id": alice["id"],
            "target_account_id": bob["id"],
            "amount_cents": 12_345,
        },
        headers={"Idempotency-Key": "e2e-001"},
    )
    assert replay.status_code == 200
    assert replay.headers["Idempotent-Replayed"] == "true"
    assert replay.json()["transfer_id"] == body["transfer_id"]

    assert client.get(f"/accounts/{alice['id']}").json()["balance_cents"] == 37_655
    assert client.get(f"/accounts/{bob['id']}").json()["balance_cents"] == 12_345

    today = datetime.now(UTC).date().isoformat()
    statement = client.get(
        f"/accounts/{alice['id']}/statement",
        params={"start_date": today},
    ).json()
    assert statement["balance_cents"] == 37_655
    assert [(t["type"], t["amount_cents"]) for t in statement["transactions"]] == [
        ("CREDIT", 50_000),
        ("DEBIT", 12_345),
    ]
    assert statement["summary"] == {
        "total_credits_cents": 50_000,
        "total_debits_cents": 12_345,
        "net_cents": 37_655,
        "count": 2,
    }

    debits_only = client.get(f"/accounts/{alice['id']}/statement", params={"type": "debit"}).json()
    assert [t["transfer_id"] for t in debits_only["transactions"]] == [body["transfer_id"]]

    antifraud.notify_transfer.assert_called_once()


def test_cross_currency_transfer_over_http(client):
    usd = create_account(client, 3, balance=10_000, currency="USD")
    brl = create_account(client, 4)
    response = client.post(
        "/transfers",
        json={"source_account_id": usd["id"], "target_account_id": brl["id"], "amount_cents": 100},
        headers={"Idempotency-Key": "fx-1"},
    )
    assert response.status_code == 201
    assert response.json()["credited_cents"] == 540


@pytest.mark.parametrize(
    ("payload_amount", "expected_status", "error"),
    [(999_999, 422, "insufficient_funds"), (0, 422, "invalid_amount")],
)
def test_transfer_business_errors(client, payload_amount, expected_status, error):
    a, b = create_account(client, 5, balance=100), create_account(client, 6)
    response = client.post(
        "/transfers",
        json={
            "source_account_id": a["id"],
            "target_account_id": b["id"],
            "amount_cents": payload_amount,
        },
        headers={"Idempotency-Key": "err-1"},
    )
    assert response.status_code == expected_status
    assert response.json()["error"] == error


def test_missing_idempotency_header_is_rejected(client):
    response = client.post(
        "/transfers", json={"source_account_id": "a", "target_account_id": "b", "amount_cents": 1}
    )
    assert response.status_code == 422


def test_account_errors(client):
    assert client.get("/accounts/missing").status_code == 404
    assert client.get("/accounts/missing/statement").json()["error"] == "account_not_found"

    invalid_cpf = client.post(
        "/accounts", json={"holder_name": "Ana Souza", "document": "12345678900"}
    )
    assert (invalid_cpf.status_code, invalid_cpf.json()["error"]) == (422, "invalid_holder")

    create_account(client, 9)
    duplicate = client.post("/accounts", json={"holder_name": "Ana Souza", "document": make_cpf(9)})
    assert duplicate.status_code == 409


def test_statement_rejects_unknown_type(client):
    account = create_account(client, 10)
    response = client.get(f"/accounts/{account['id']}/statement", params={"type": "refund"})
    assert (response.status_code, response.json()["error"]) == (422, "invalid_request")


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"
