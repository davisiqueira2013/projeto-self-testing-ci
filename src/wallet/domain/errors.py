"""Erros de domínio. A camada HTTP traduz cada código para um status."""


class DomainError(Exception):
    code = "domain_error"


class InvalidAmountError(DomainError):
    code = "invalid_amount"


class UnsupportedCurrencyError(DomainError):
    code = "unsupported_currency"


class SameAccountTransferError(DomainError):
    code = "same_account_transfer"


class InsufficientFundsError(DomainError):
    code = "insufficient_funds"

    def __init__(self, account_id: str, balance_cents: int, requested_cents: int) -> None:
        super().__init__(
            f"account {account_id} has {balance_cents} cents, requested {requested_cents}"
        )
        self.account_id = account_id
        self.balance_cents = balance_cents
        self.requested_cents = requested_cents


class AccountNotFoundError(DomainError):
    code = "account_not_found"

    def __init__(self, account_id: str) -> None:
        super().__init__(f"account {account_id} not found")
        self.account_id = account_id


class DuplicateAccountError(DomainError):
    code = "duplicate_account"


class InvalidHolderError(DomainError):
    code = "invalid_holder"


class InvalidRequestError(DomainError):
    code = "invalid_request"
