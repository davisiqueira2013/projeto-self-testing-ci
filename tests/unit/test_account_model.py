import pytest

from tests.support import make_account
from wallet.domain.errors import InsufficientFundsError, InvalidAmountError


class TestDebit:
    def test_debit_reduces_balance(self):
        account = make_account(1_000)
        account.debit(300)
        assert account.balance_cents == 700

    def test_debit_of_entire_balance_leaves_zero(self):
        account = make_account(1_000)
        account.debit(1_000)
        assert account.balance_cents == 0

    def test_debit_above_balance_raises_and_keeps_balance(self):
        account = make_account(100)
        with pytest.raises(InsufficientFundsError) as exc:
            account.debit(101)
        assert account.balance_cents == 100
        assert (exc.value.account_id, exc.value.balance_cents, exc.value.requested_cents) == (
            "acc-1",
            100,
            101,
        )

    @pytest.mark.parametrize("amount", [0, -5])
    def test_debit_rejects_invalid_amount(self, amount):
        with pytest.raises(InvalidAmountError):
            make_account().debit(amount)


class TestCredit:
    def test_credit_increases_balance(self):
        account = make_account(0)
        account.credit(250)
        assert account.balance_cents == 250

    def test_credit_has_no_upper_limit(self):
        account = make_account(0)
        account.credit(10**12)
        assert account.balance_cents == 10**12

    def test_credit_rejects_negative(self):
        with pytest.raises(InvalidAmountError):
            make_account().credit(-1)


@pytest.mark.parametrize(("balance", "amount", "expected"), [(10, 10, True), (10, 11, False)])
def test_can_debit(balance, amount, expected):
    assert make_account(balance).can_debit(amount) is expected
