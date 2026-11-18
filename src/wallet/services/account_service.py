from __future__ import annotations

from wallet.domain.errors import AccountNotFoundError, InvalidAmountError, InvalidHolderError
from wallet.domain.models import Account, Transaction, TransactionType
from wallet.domain.rules import normalize_document, validate_currency
from wallet.gateways.kyc import KycProvider
from wallet.repositories.sqlite import SqliteWalletRepository
from wallet.services.common import Clock, IdFactory, new_id, utcnow


class AccountService:
    def __init__(
        self,
        repository: SqliteWalletRepository,
        kyc: KycProvider,
        clock: Clock = utcnow,
        id_factory: IdFactory = new_id,
    ) -> None:
        self._repo = repository
        self._kyc = kyc
        self._clock = clock
        self._new_id = id_factory

    def open_account(
        self,
        holder_name: str,
        document: str,
        currency: str = "BRL",
        initial_balance_cents: int = 0,
    ) -> Account:
        currency = validate_currency(currency)
        if (
            isinstance(initial_balance_cents, bool)
            or not isinstance(initial_balance_cents, int)
            or initial_balance_cents < 0
        ):
            raise InvalidAmountError("initial balance must be a non-negative integer")
        document = normalize_document(document)
        holder_name = holder_name.strip()

        verdict = self._kyc.validate(holder_name, document)
        if not verdict.approved:
            raise InvalidHolderError(verdict.reason or "holder rejected by KYC")

        now = self._clock()
        account = Account(self._new_id(), holder_name, document, currency, 0, now)
        with self._repo.atomic():
            self._repo.add_account(account)
            if initial_balance_cents > 0:
                account.credit(initial_balance_cents)
                self._repo.save_balance(account)
                self._repo.add_transaction(
                    Transaction(
                        id=self._new_id(),
                        account_id=account.id,
                        type=TransactionType.CREDIT,
                        amount_cents=initial_balance_cents,
                        balance_after_cents=account.balance_cents,
                        created_at=now,
                        description="Saldo inicial",
                    )
                )
        return account

    def get_account(self, account_id: str) -> Account:
        account = self._repo.get_account(account_id)
        if account is None:
            raise AccountNotFoundError(account_id)
        return account
