from __future__ import annotations

import hashlib
import logging

from wallet.domain.errors import (
    AccountNotFoundError,
    InvalidRequestError,
)
from wallet.domain.models import Account, Transaction, TransactionType, TransferResult
from wallet.domain.rules import is_high_risk, plan_transfer
from wallet.gateways.antifraud import AntiFraudGateway
from wallet.gateways.fx import ExchangeRateProvider
from wallet.repositories.sqlite import SqliteWalletRepository
from wallet.services.common import Clock, IdFactory, new_id, utcnow

logger = logging.getLogger(__name__)

MAX_IDEMPOTENCY_KEY_LENGTH = 128


class TransferService:
    def __init__(
        self,
        repository: SqliteWalletRepository,
        antifraud: AntiFraudGateway,
        fx: ExchangeRateProvider,
        *,
        high_risk_threshold_cents: int = 500_000,
        clock: Clock = utcnow,
        id_factory: IdFactory = new_id,
    ) -> None:
        self._repo = repository
        self._antifraud = antifraud
        self._fx = fx
        self._threshold = high_risk_threshold_cents
        self._clock = clock
        self._new_id = id_factory

    def transfer(
        self,
        source_account_id: str,
        target_account_id: str,
        amount_cents: int,
        idempotency_key: str,
    ) -> tuple[TransferResult, bool]:
        """Executa a transferência. Retorna ``(resultado, replayed)``."""
        key = (idempotency_key or "").strip()
        if not key or len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
            raise InvalidRequestError("Idempotency-Key must have 1 to 128 characters")
        request_hash = _hash_request(source_account_id, target_account_id, amount_cents)

        with self._repo.atomic():
            previous = self._repo.get_idempotency(key)
            if previous is not None:
                return TransferResult.from_dict(previous.response), True

            source = self._load(source_account_id)
            target = self._load(target_account_id)
            rate = self._fx.get_rate(source.currency, target.currency)
            debit_cents, credit_cents = plan_transfer(source, target, amount_cents, rate)

            source.debit(debit_cents)
            target.credit(credit_cents)
            now = self._clock()
            result = TransferResult(
                transfer_id=self._new_id(),
                source_account_id=source.id,
                target_account_id=target.id,
                amount_cents=debit_cents,
                credited_cents=credit_cents,
                source_currency=source.currency,
                target_currency=target.currency,
                exchange_rate=str(rate),
                created_at=now.isoformat(),
            )
            self._persist(source, target, result, now)
            self._repo.save_idempotency(key, request_hash, result.to_dict(), now)

        self._notify_antifraud(result)
        return result, False

    def _load(self, account_id: str) -> Account:
        account = self._repo.get_account(account_id)
        if account is None:
            raise AccountNotFoundError(account_id)
        return account

    def _persist(self, source: Account, target: Account, result: TransferResult, now) -> None:
        self._repo.save_balance(source)
        self._repo.save_balance(target)
        for account, tx_type, amount, counterparty in (
            (source, TransactionType.DEBIT, result.amount_cents, target.id),
            (target, TransactionType.CREDIT, result.credited_cents, source.id),
        ):
            self._repo.add_transaction(
                Transaction(
                    id=self._new_id(),
                    account_id=account.id,
                    type=tx_type,
                    amount_cents=amount,
                    balance_after_cents=account.balance_cents,
                    created_at=now,
                    transfer_id=result.transfer_id,
                    counterparty_account_id=counterparty,
                    description="Transferência",
                )
            )

    def _notify_antifraud(self, result: TransferResult) -> None:
        event = {
            "event": "transfer.completed",
            "transfer_id": result.transfer_id,
            "source_account_id": result.source_account_id,
            "target_account_id": result.target_account_id,
            "amount_cents": result.amount_cents,
            "currency": result.source_currency,
            "high_risk": is_high_risk(result.amount_cents, self._threshold),
            "occurred_at": result.created_at,
        }
        try:
            self._antifraud.notify_transfer(event)
        except Exception:  # a transferência já foi confirmada; falha externa não a desfaz
            logger.warning(
                "antifraud notification failed for transfer %s",
                result.transfer_id,
                exc_info=True,
            )


def _hash_request(source: str, target: str, amount_cents: int) -> str:
    return hashlib.sha256(f"{source}|{target}|{amount_cents}".encode()).hexdigest()
