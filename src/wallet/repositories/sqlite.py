"""Repositório SQLite (arquivo ou ``:memory:``) com transações serializadas."""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

from wallet.domain.errors import DuplicateAccountError
from wallet.domain.models import Account, Transaction, TransactionType

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id            TEXT PRIMARY KEY,
    holder_name   TEXT NOT NULL,
    document      TEXT NOT NULL UNIQUE,
    currency      TEXT NOT NULL,
    balance_cents INTEGER NOT NULL CHECK (balance_cents >= 0),
    created_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transactions (
    id                      TEXT PRIMARY KEY,
    account_id              TEXT NOT NULL REFERENCES accounts(id),
    type                    TEXT NOT NULL CHECK (type IN ('DEBIT', 'CREDIT')),
    amount_cents            INTEGER NOT NULL CHECK (amount_cents > 0),
    balance_after_cents     INTEGER NOT NULL,
    transfer_id             TEXT,
    counterparty_account_id TEXT,
    description             TEXT NOT NULL DEFAULT '',
    created_at              TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_transactions_account_date
    ON transactions (account_id, created_at);
CREATE TABLE IF NOT EXISTS idempotency_keys (
    key           TEXT PRIMARY KEY,
    request_hash  TEXT NOT NULL,
    response_json TEXT NOT NULL,
    created_at    TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class IdempotencyRecord:
    key: str
    request_hash: str
    response: dict


class SqliteWalletRepository:
    def __init__(self, database: str = ":memory:") -> None:
        self._conn = sqlite3.connect(database, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._depth = 0
        self._conn.execute("PRAGMA foreign_keys = ON")
        if database != ":memory:":
            self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.executescript(SCHEMA)

    @contextmanager
    def atomic(self) -> Iterator[SqliteWalletRepository]:
        """Unidade de trabalho: lock de processo + ``BEGIN IMMEDIATE`` no SQLite."""
        with self._lock:
            outermost = self._depth == 0
            if outermost:
                self._conn.execute("BEGIN IMMEDIATE")
            self._depth += 1
            try:
                yield self
            except BaseException:
                self._depth -= 1
                if outermost:
                    self._conn.execute("ROLLBACK")
                raise
            self._depth -= 1
            if outermost:
                self._conn.execute("COMMIT")

    # ---- contas -------------------------------------------------------------
    def add_account(self, account: Account) -> None:
        try:
            with self._lock:
                self._conn.execute(
                    "INSERT INTO accounts VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        account.id,
                        account.holder_name,
                        account.document,
                        account.currency,
                        account.balance_cents,
                        account.created_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise DuplicateAccountError("an account with this document already exists") from exc

    def get_account(self, account_id: str) -> Account | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM accounts WHERE id = ?", (account_id,)
            ).fetchone()
        if row is None:
            return None
        return Account(
            id=row["id"],
            holder_name=row["holder_name"],
            document=row["document"],
            currency=row["currency"],
            balance_cents=row["balance_cents"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def save_balance(self, account: Account) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE accounts SET balance_cents = ? WHERE id = ?",
                (account.balance_cents, account.id),
            )

    # ---- transações ---------------------------------------------------------
    def add_transaction(self, tx: Transaction) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    tx.id,
                    tx.account_id,
                    tx.type.value,
                    tx.amount_cents,
                    tx.balance_after_cents,
                    tx.transfer_id,
                    tx.counterparty_account_id,
                    tx.description,
                    tx.created_at.isoformat(),
                ),
            )

    def list_transactions(
        self,
        account_id: str,
        start: datetime | None = None,
        end: datetime | None = None,
        tx_type: TransactionType | None = None,
    ) -> list[Transaction]:
        """Lista transações com ``start <= created_at < end`` (fim exclusivo)."""
        sql = ["SELECT * FROM transactions WHERE account_id = ?"]
        params: list[object] = [account_id]
        if start is not None:
            sql.append("AND created_at >= ?")
            params.append(start.isoformat())
        if end is not None:
            sql.append("AND created_at < ?")
            params.append(end.isoformat())
        if tx_type is not None:
            sql.append("AND type = ?")
            params.append(tx_type.value)
        sql.append("ORDER BY created_at, rowid")
        with self._lock:
            rows = self._conn.execute(" ".join(sql), params).fetchall()
        return [
            Transaction(
                id=r["id"],
                account_id=r["account_id"],
                type=TransactionType(r["type"]),
                amount_cents=r["amount_cents"],
                balance_after_cents=r["balance_after_cents"],
                created_at=datetime.fromisoformat(r["created_at"]),
                transfer_id=r["transfer_id"],
                counterparty_account_id=r["counterparty_account_id"],
                description=r["description"],
            )
            for r in rows
        ]

    # ---- idempotência -------------------------------------------------------
    def get_idempotency(self, key: str) -> IdempotencyRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM idempotency_keys WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        return IdempotencyRecord(row["key"], row["request_hash"], json.loads(row["response_json"]))

    def save_idempotency(self, key: str, request_hash: str, response: dict, at: datetime) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO idempotency_keys VALUES (?, ?, ?, ?)",
                (key, request_hash, json.dumps(response), at.isoformat()),
            )

    def close(self) -> None:
        self._conn.close()
