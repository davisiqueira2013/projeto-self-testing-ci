# Relatório Técnico — Wallet API (projeto-self-testing-ci)

> Projeto Capstone: API de microsserviço financeiro com automação de CI, suíte de
> self-testing multinível e estratégia de branching.

## Links

| Item | Link |
|------|------|
| Repositório | `https://github.com/<usuario>/projeto-self-testing-ci` *(substituir após o push)* |
| Execuções do pipeline | `https://github.com/<usuario>/projeto-self-testing-ci/actions` |
| Pipeline | [`.github/workflows/ci.yml`](.github/workflows/ci.yml) |
| Script de carga | [`load/locustfile.py`](load/locustfile.py) |
| Evidência de carga | [`docs/evidencias/load-test-summary.json`](docs/evidencias/load-test-summary.json) |

---

## 1. Visão geral e escopo

A Wallet API é um microsserviço REST de carteira digital e conciliação bancária. Ela oferece:

1. criação e consulta de contas digitais com saldo inicial;
2. transferência entre contas com controle de concorrência, saldo insuficiente e idempotência;
3. extrato com filtros por período e por tipo de transação (débito/crédito);
4. integração com um gateway anti-fraude externo fictício, que recebe um webhook a cada transferência.

**Stack:** Python 3.13, FastAPI, SQLite (arquivo em produção, `:memory:` nos testes), PyTest,
pytest-cov (Coverage.py), Ruff, Locust e GitHub Actions.

## 2. Especificação de Requisitos de Software (SRS)

### 2.1 Atores

| Ator | Descrição |
|------|-----------|
| Cliente da API | Sistema consumidor (app, internet banking) que opera contas e transferências. |
| Gateway anti-fraude | Serviço externo que recebe eventos de transferência via webhook. |
| Provedor cadastral (KYC) | Valida os dados do titular (nome e CPF). |
| Provedor de câmbio | Fornece a taxa de conversão entre moedas. |

### 2.2 Requisitos funcionais

| ID | Requisito | Critério de aceitação |
|----|-----------|-----------------------|
| RF01 | Criar uma conta com titular, CPF, moeda (BRL/USD/EUR) e saldo inicial ≥ 0. | `POST /accounts` retorna 201. Se o saldo inicial for maior que zero, gera um lançamento de crédito "Saldo inicial". |
| RF02 | Validar o cadastro (KYC) antes de criar a conta. | CPF inválido ou nome com menos de 3 caracteres → 422 `invalid_holder`. |
| RF03 | Impedir duas contas com o mesmo CPF. | 409 `duplicate_account`. |
| RF04 | Consultar uma conta e o seu saldo. | `GET /accounts/{id}` → 200, ou 404 se a conta não existir. |
| RF05 | Transferir valores entre contas de forma atômica. | Débito e crédito são gravados na mesma transação. Se algo falhar, nada é gravado. |
| RF06 | Recusar uma transferência sem saldo suficiente. | 422 `insufficient_funds`. Os saldos não mudam e o anti-fraude não é notificado. |
| RF07 | Garantir idempotência pelo header `Idempotency-Key`. | Repetir a mesma chave com o mesmo payload → 200 com o mesmo resultado e sem novo débito. Mesma chave com payload diferente → 409 `idempotency_conflict`. |
| RF08 | Converter o valor quando as moedas das contas forem diferentes. | O crédito é igual ao débito × taxa, com arredondamento bancário (HALF_EVEN). |
| RF09 | Emitir o extrato com filtros `start_date`, `end_date` (inclusivos) e `type`. | Lista ordenada por data, com totais de crédito, débito e líquido. Período invertido → 422. |
| RF10 | Notificar o gateway anti-fraude a cada transferência efetivada. | Webhook `transfer.completed` com conta de origem, conta de destino, valor, moeda e `high_risk` (valor ≥ limiar configurável). |

### 2.3 Requisitos não funcionais

| ID | Categoria | Requisito |
|----|-----------|-----------|
| RNF01 | Consistência | Nenhuma condição de corrida pode gerar saldo negativo nem criar ou destruir dinheiro. A soma dos saldos se conserva sob concorrência. |
| RNF02 | Desempenho | Com 50 requisições simultâneas em `POST /transfers`: taxa de erro igual a 0% e latência média abaixo de 200 ms em ambiente de CI. |
| RNF03 | Resiliência | Uma falha do gateway anti-fraude não desfaz uma transferência já confirmada. A falha é registrada em log (WARNING). |
| RNF04 | Precisão monetária | Valores sempre em centavos inteiros e conversões com `Decimal`, sem uso de `float`. |
| RNF05 | Qualidade | Cobertura mínima de 85% das linhas e de 80% dos branches, verificada automaticamente no CI. |
| RNF06 | Manutenibilidade | Lint e formatação com Ruff e complexidade ciclomática de no máximo 10 por função. |
| RNF07 | Configurabilidade | Toda a configuração vem de variáveis de ambiente (`.env.example`), sem segredos no código. |
| RNF08 | Rastreabilidade | Commits seguem Conventional Commits. `main` e `develop` só recebem código por merge validado. |

### 2.4 Regras de negócio

* **RN01:** o valor de uma transferência deve ser um inteiro entre 1 e 100.000.000 centavos (R$ 1 milhão).
* **RN02:** a conta de origem deve ser diferente da conta de destino.
* **RN03:** uma conversão que arredonda para zero centavos é rejeitada.
* **RN04:** a `Idempotency-Key` deve ter de 1 a 128 caracteres e é registrada **na mesma transação** da transferência.
* **RN05:** o banco de dados também protege os saldos: `CHECK (balance_cents >= 0)`.

### 2.5 Rastreabilidade entre requisitos e testes

| Requisito | Testes |
|-----------|--------|
| RF01–RF04 | `tests/integration/test_account_service.py`, `tests/e2e/test_wallet_flow.py::test_account_errors` |
| RF05, RF06 | `tests/unit/test_transfer_rules.py`, `tests/integration/test_transfer_service.py` |
| RF07 | `test_same_idempotency_key_*`, `test_reusing_idempotency_key_*`, `test_idempotency_conflict_returns_409` |
| RF08 | `tests/unit/test_amount_rules.py::TestConvert`, `test_cross_currency_*` (integração e E2E) |
| RF09 | `tests/integration/test_statement_service.py`, fluxo E2E |
| RF10, RNF03 | `test_antifraud_mock_*`, `test_antifraud_failure_does_not_roll_back_committed_transfer` |
| RNF01 | `test_concurrent_transfers_never_overdraw_and_conserve_money` e o teste de carga (`money_conserved`) |
| RNF05 | `scripts/check_coverage.py` e `tests/unit/test_coverage_gate.py` |
