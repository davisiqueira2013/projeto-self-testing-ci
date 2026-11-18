from decimal import Decimal

import pytest
from wallet.domain.errors import InvalidAmountError, UnsupportedCurrencyError
from wallet.domain.rules import (
    MAX_TRANSFER_CENTS,
    convert,
    is_high_risk,
    validate_amount,
    validate_currency,
)


class TestValidateAmount:
    @pytest.mark.parametrize("amount", [1, 150, MAX_TRANSFER_CENTS])
    def test_accepts_positive_integer_cents_within_limit(self, amount):
        assert validate_amount(amount) == amount

    @pytest.mark.parametrize("amount", [0, -1, -10_000])
    def test_rejects_zero_and_negative(self, amount):
        with pytest.raises(InvalidAmountError, match="positive"):
            validate_amount(amount)

    @pytest.mark.parametrize("amount", [10.5, "100", None, True, Decimal("1")])
    def test_rejects_non_integer_values(self, amount):
        with pytest.raises(InvalidAmountError, match="integer"):
            validate_amount(amount)

    def test_rejects_amount_above_limit(self):
        with pytest.raises(InvalidAmountError, match="limit"):
            validate_amount(MAX_TRANSFER_CENTS + 1)

    def test_limit_can_be_disabled(self):
        assert validate_amount(MAX_TRANSFER_CENTS * 10, maximum=None) == MAX_TRANSFER_CENTS * 10


class TestValidateCurrency:
    @pytest.mark.parametrize(
        ("raw", "expected"), [("brl", "BRL"), (" usd ", "USD"), ("EUR", "EUR")]
    )
    def test_normalizes_supported_currencies(self, raw, expected):
        assert validate_currency(raw) == expected

    @pytest.mark.parametrize("raw", ["JPY", "", None])
    def test_rejects_unsupported(self, raw):
        with pytest.raises(UnsupportedCurrencyError):
            validate_currency(raw)


class TestConvert:
    def test_multiplies_by_rate(self):
        assert convert(100, Decimal("5.40")) == 540

    def test_uses_bankers_rounding_half_even(self):
        # 25 * 0.5 = 12.5 -> 12 (par) ; 35 * 0.5 = 17.5 -> 18 (par)
        assert convert(25, Decimal("0.5")) == 12
        assert convert(35, Decimal("0.5")) == 18

    @pytest.mark.parametrize("rate", [Decimal("0"), Decimal("-1.2")])
    def test_rejects_non_positive_rate(self, rate):
        with pytest.raises(InvalidAmountError, match="rate"):
            convert(100, rate)

    def test_rejects_conversion_that_rounds_to_zero(self):
        with pytest.raises(InvalidAmountError, match="zero"):
            convert(1, Decimal("0.2"))


class TestHighRisk:
    @pytest.mark.parametrize(
        ("amount", "expected"), [(499_999, False), (500_000, True), (500_001, True)]
    )
    def test_threshold_is_inclusive(self, amount, expected):
        assert is_high_risk(amount, 500_000) is expected
