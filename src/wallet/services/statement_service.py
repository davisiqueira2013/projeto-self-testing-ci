from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time

from wallet.domain.errors import AccountNotFoundError, InvalidRequestError
from wallet.domain.models import Account, Transaction, TransactionType
from wallet.domain.rules import StatementSummary, summarize
from wallet.repositories.sqlite import SqliteWalletRepository


@dataclass(frozen=True)
class Statement:
    account: Account
    transactions: list[Transaction]
    summary: StatementSummary
    start_date: date | None
    end_date: date | None
    type: TransactionType | None


class StatementService:
    def __init__(self, repository: SqliteWalletRepository) -> None:
        self._repo = repository

    def get_statement(
        self,
        account_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
        tx_type: TransactionType | None = None,
    ) -> Statement:
        account = self._repo.get_account(account_id)
        if account is None:
            raise AccountNotFoundError(account_id)
        if start_date and end_date and start_date > end_date:
            raise InvalidRequestError("start_date must be before or equal to end_date")

        start = datetime.combine(start_date, time.min, UTC) if start_date else None
        end = datetime.combine(end_date, time.min, UTC) if end_date else None
        transactions = self._repo.list_transactions(account_id, start, end, tx_type)
        return Statement(
            account, transactions, summarize(transactions), start_date, end_date, tx_type
        )
