from decimal import Decimal

import pytest

from wallet.config import Settings, parse_fx_rates
from wallet.domain.errors import UnsupportedCurrencyError
from wallet.gateways.fx import StaticExchangeRateProvider


class TestStaticExchangeRateProvider:
    provider = StaticExchangeRateProvider({"usd": Decimal("5.40"), "EUR": Decimal("5.85")})

    def test_same_currency_rate_is_one(self):
        assert self.provider.get_rate("USD", "USD") == Decimal("1")

    def test_rate_to_brl(self):
        assert self.provider.get_rate("USD", "BRL") == Decimal("5.40")

    def test_cross_rate_is_derived_from_brl(self):
        assert self.provider.get_rate("BRL", "USD") == Decimal("0.185185")
        assert self.provider.get_rate("EUR", "USD") == Decimal("1.083333")

    def test_unknown_currency(self):
        with pytest.raises(UnsupportedCurrencyError, match="GBP"):
            self.provider.get_rate("GBP", "BRL")


class TestParseFxRates:
    def test_parses_list(self):
        assert parse_fx_rates("USD=5.40, eur=5.85,") == {
            "USD": Decimal("5.40"),
            "EUR": Decimal("5.85"),
        }

    @pytest.mark.parametrize("raw", ["USD5.40", "USD=abc", "USD=0", "USD=-1"])
    def test_rejects_invalid_entries(self, raw):
        with pytest.raises(ValueError, match="FX rate"):
            parse_fx_rates(raw)


class TestSettings:
    def test_defaults_when_env_is_empty(self):
        settings = Settings.from_env({})
        assert settings.database_path == ":memory:"
        assert settings.antifraud_webhook_url is None
        assert settings.fx_rates_to_brl["USD"] == Decimal("5.40")

    def test_reads_values_from_env(self):
        settings = Settings.from_env(
            {
                "DATABASE_PATH": "/tmp/w.db",
                "ANTIFRAUD_WEBHOOK_URL": "https://fraud.example/hook",
                "ANTIFRAUD_TIMEOUT_SECONDS": "0.5",
                "HIGH_RISK_THRESHOLD_CENTS": "100",
                "FX_RATES_TO_BRL": "USD=6",
            }
        )
        assert settings.database_path == "/tmp/w.db"
        assert settings.antifraud_webhook_url == "https://fraud.example/hook"
        assert settings.antifraud_timeout_seconds == 0.5
        assert settings.high_risk_threshold_cents == 100
        assert settings.fx_rates_to_brl == {"USD": Decimal("6")}
