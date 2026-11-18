"""Teste de carga do endpoint POST /transfers com Locust.

Execução (50 usuários simultâneos, sem espera entre requisições):

    locust -f load/locustfile.py --headless -u 50 -r 50 -t 30s --host http://127.0.0.1:8000

Antes do teste são criadas ``LOAD_ACCOUNTS`` contas com saldo alto; os usuários
transferem valores aleatórios entre pares aleatórios (alta contenção). Ao final,
o script:
  * grava ``reports/load/summary.json`` com taxa de erro, latência média e p95;
  * verifica a conservação do dinheiro (soma dos saldos inalterada);
  * retorna código de saída 1 se houver erro, travamento ou inconsistência.
"""

from __future__ import annotations

import json
import os
import random
import uuid
from pathlib import Path

import requests
from locust import HttpUser, constant, events, task

ACCOUNT_COUNT = int(os.getenv("LOAD_ACCOUNTS", "10"))
INITIAL_BALANCE = 100_000_000  # R$ 1.000.000,00 por conta
MAX_ERROR_RATE = float(os.getenv("LOAD_MAX_ERROR_RATE", "0.0"))
REPORT = Path(os.getenv("LOAD_REPORT", "reports/load/summary.json"))

ACCOUNTS: list[str] = []


def _cpf(seed: int) -> str:
    base = f"{(seed * 7919 + 987_654_321) % 1_000_000_000:09d}"

    def digit(digits: str) -> str:
        weight = len(digits) + 1
        rest = (sum(int(d) * (weight - i) for i, d in enumerate(digits)) * 10) % 11
        return "0" if rest == 10 else str(rest)

    first = digit(base)
    return base + first + digit(base + first)


@events.test_start.add_listener
def seed_accounts(environment, **_):
    run = random.randint(0, 10**6)
    for i in range(ACCOUNT_COUNT):
        response = requests.post(
            f"{environment.host}/accounts",
            json={
                "holder_name": f"Carga {i:02d}",
                "document": _cpf(run * 100 + i),
                "initial_balance_cents": INITIAL_BALANCE,
            },
            timeout=5,
        )
        response.raise_for_status()
        ACCOUNTS.append(response.json()["id"])


class TransferUser(HttpUser):
    wait_time = constant(0)

    @task
    def transfer(self):
        source, target = random.sample(ACCOUNTS, 2)
        self.client.post(
            "/transfers",
            json={
                "source_account_id": source,
                "target_account_id": target,
                "amount_cents": random.randint(1, 5_000),
            },
            headers={"Idempotency-Key": uuid.uuid4().hex},
            name="POST /transfers",
        )


@events.quitting.add_listener
def summarize(environment, **_):
    stats = environment.stats.get("POST /transfers", "POST")
    total = stats.num_requests
    error_rate = stats.num_failures / total if total else 1.0

    balances = [
        requests.get(f"{environment.host}/accounts/{acc}", timeout=5).json()["balance_cents"]
        for acc in ACCOUNTS
    ]
    conserved = sum(balances) == INITIAL_BALANCE * len(ACCOUNTS)

    summary = {
        "users": environment.parsed_options.num_users if environment.parsed_options else None,
        "requests": total,
        "failures": stats.num_failures,
        "error_rate_percent": round(error_rate * 100, 3),
        "avg_latency_ms": round(stats.avg_response_time, 2),
        "median_latency_ms": stats.median_response_time,
        "p95_latency_ms": stats.get_response_time_percentile(0.95),
        "p99_latency_ms": stats.get_response_time_percentile(0.99),
        "max_latency_ms": round(stats.max_response_time, 2),
        "throughput_rps": round(stats.total_rps, 2),
        "money_conserved": conserved,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(summary, indent=2))
    print("\n=== Resumo do teste de carga ===")
    print(json.dumps(summary, indent=2))

    if total == 0 or error_rate > MAX_ERROR_RATE or not conserved:
        environment.process_exit_code = 1
