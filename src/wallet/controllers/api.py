from __future__ import annotations

from dataclasses import asdict
from datetime import date

from fastapi import FastAPI, Header, Query, Request, Response, status
from fastapi.responses import JSONResponse

from wallet import __version__
from wallet.config import Settings
from wallet.container import Container, build_container
from wallet.controllers.schemas import (
    AccountIn,
    AccountOut,
    StatementOut,
    SummaryOut,
    TransactionOut,
    TransferIn,
    TransferOut,
)
from wallet.domain import errors
from wallet.domain.models import Account, TransactionType

STATUS_BY_ERROR: dict[type[errors.DomainError], int] = {
    errors.AccountNotFoundError: status.HTTP_404_NOT_FOUND,
    errors.DuplicateAccountError: status.HTTP_409_CONFLICT,
}


def _account_out(account: Account) -> AccountOut:
    return AccountOut(**asdict(account))


def create_app(container: Container | None = None) -> FastAPI:
    container = container or build_container(Settings.from_env())
    app = FastAPI(title="Wallet API", version=__version__)
    app.state.container = container

    @app.exception_handler(errors.DomainError)
    def handle_domain_error(_: Request, exc: errors.DomainError) -> JSONResponse:
        code = STATUS_BY_ERROR.get(type(exc), 422)
        return JSONResponse(status_code=code, content={"error": exc.code, "message": str(exc)})

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    @app.post("/accounts", status_code=status.HTTP_201_CREATED, response_model=AccountOut)
    def open_account(body: AccountIn) -> AccountOut:
        account = container.accounts.open_account(
            body.holder_name, body.document, body.currency, body.initial_balance_cents
        )
        return _account_out(account)

    @app.get("/accounts/{account_id}", response_model=AccountOut)
    def get_account(account_id: str) -> AccountOut:
        return _account_out(container.accounts.get_account(account_id))

    @app.post("/transfers", status_code=status.HTTP_201_CREATED, response_model=TransferOut)
    def transfer(
        body: TransferIn,
        response: Response,
        idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128),
    ) -> TransferOut:
        result, replayed = container.transfers.transfer(
            body.source_account_id, body.target_account_id, body.amount_cents, idempotency_key
        )
        if replayed:
            response.status_code = status.HTTP_200_OK
            response.headers["Idempotent-Replayed"] = "true"
        return TransferOut(**result.to_dict())

    @app.get("/accounts/{account_id}/statement", response_model=StatementOut)
    def statement(
        account_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
        tx_type: str | None = Query(default=None, alias="type"),
    ) -> StatementOut:
        parsed_type = _parse_type(tx_type)
        st = container.statements.get_statement(account_id, start_date, end_date, parsed_type)
        return StatementOut(
            account_id=st.account.id,
            currency=st.account.currency,
            balance_cents=st.account.balance_cents,
            start_date=st.start_date,
            end_date=st.end_date,
            type=parsed_type.value if parsed_type else None,
            summary=SummaryOut(
                total_credits_cents=st.summary.total_credits_cents,
                total_debits_cents=st.summary.total_debits_cents,
                net_cents=st.summary.net_cents,
                count=st.summary.count,
            ),
            transactions=[
                TransactionOut(**{k: v for k, v in asdict(tx).items() if k != "account_id"})
                for tx in st.transactions
            ],
        )

    return app


def _parse_type(raw: str | None) -> TransactionType | None:
    if raw is None:
        return None
    try:
        return TransactionType(raw.strip().upper())
    except ValueError as exc:
        raise errors.InvalidRequestError("type must be DEBIT or CREDIT") from exc
