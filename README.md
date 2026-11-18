# Wallet API — projeto-self-testing-ci

API REST de carteira digital e conciliação bancária (Python 3.13 + FastAPI + SQLite), com
suíte self-testing multinível (unitário → integração → E2E), pipeline de CI no GitHub Actions
com coverage gate e teste de carga com Locust.

A documentação completa (requisitos, arquitetura, estratégia de branching, evidências de TDD,
métricas de cobertura e de carga) está em [`RELATORIO_TECNICO.md`](RELATORIO_TECNICO.md).

## Como executar

```bash
python -m venv .venv && source .venv/bin/activate
make install            # dependências de produção e de desenvolvimento
cp .env.example .env    # opcional: configure webhook anti-fraude e câmbio
make run                # API em http://127.0.0.1:8000 (docs em /docs)
```

| Comando              | O que faz                                                        |
|----------------------|------------------------------------------------------------------|
| `make lint`          | Ruff (lint, imports, complexidade) + verificação de formatação   |
| `make test`          | Unitários, integração e E2E, acumulando cobertura                |
| `make coverage-gate` | Gera relatórios e falha se linhas < 85% ou branches < 80%        |
| `make load`          | Sobe a API e roda Locust com 50 usuários em `POST /transfers`    |

## Endpoints

| Método | Rota                                   | Descrição                                        |
|--------|----------------------------------------|--------------------------------------------------|
| POST   | `/accounts`                            | Cria conta (KYC por CPF, saldo inicial opcional) |
| GET    | `/accounts/{id}`                       | Consulta conta e saldo                           |
| POST   | `/transfers` + header `Idempotency-Key`| Transferência atômica e idempotente              |
| GET    | `/accounts/{id}/statement`             | Extrato com `start_date`, `end_date`, `type`     |
| GET    | `/health`                              | Health check                                     |

Valores monetários trafegam sempre em **centavos inteiros** (`amount_cents`).
