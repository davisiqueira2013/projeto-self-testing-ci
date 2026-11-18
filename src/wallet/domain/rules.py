from decimal import ROUND_HALF_EVEN, Decimal

from wallet.domain.errors import InvalidAmountError, UnsupportedCurrencyError

MAX_TRANSFER_CENTS = 100000000


def validate_amount(amount_cents, maximum=MAX_TRANSFER_CENTS):
    if type(amount_cents) is not int:
        raise InvalidAmountError("amount must be an integer number of cents")
    if amount_cents <= 0:
        raise InvalidAmountError("amount must be positive")
    if maximum is not None:
        if amount_cents > maximum:
            raise InvalidAmountError("amount exceeds the limit of " + str(maximum) + " cents")
    return amount_cents


def validate_currency(currency):
    if currency is None:
        raise UnsupportedCurrencyError("currency None is not supported")
    code = currency.strip().upper()
    if code not in ["BRL", "USD", "EUR"]:
        raise UnsupportedCurrencyError("currency " + repr(currency) + " is not supported")
    return code


def convert(amount_cents, rate):
    if rate <= 0:
        raise InvalidAmountError("exchange rate must be positive")
    value = Decimal(amount_cents) * rate
    converted = int(value.quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))
    if converted <= 0:
        raise InvalidAmountError("converted amount rounds to zero")
    return converted


def is_high_risk(amount_cents, threshold_cents):
    if amount_cents >= threshold_cents:
        return True
    return False
