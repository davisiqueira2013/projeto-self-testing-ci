from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation


def parse_fx_rates(raw: str) -> dict[str, Decimal]:
    """Converte ``"USD=5.40,EUR=5.85"`` em ``{"USD": Decimal("5.40"), ...}``."""
    rates: dict[str, Decimal] = {}
    for chunk in filter(None, (part.strip() for part in raw.split(","))):
        code, sep, value = chunk.partition("=")
        if not sep:
            raise ValueError(f"invalid FX rate entry: {chunk!r}")
        try:
            rate = Decimal(value.strip())
        except InvalidOperation as exc:
            raise ValueError(f"invalid FX rate value: {chunk!r}") from exc
        if rate <= 0:
            raise ValueError(f"FX rate must be positive: {chunk!r}")
        rates[code.strip().upper()] = rate
    return rates


@dataclass(frozen=True)
class Settings:
    database_path: str = ":memory:"
    antifraud_webhook_url: str | None = None
    antifraud_timeout_seconds: float = 2.0
    high_risk_threshold_cents: int = 500_000
    fx_rates_to_brl: dict[str, Decimal] = field(
        default_factory=lambda: {"USD": Decimal("5.40"), "EUR": Decimal("5.85")}
    )

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env
        defaults = cls()
        return cls(
            database_path=env.get("DATABASE_PATH", defaults.database_path),
            antifraud_webhook_url=env.get("ANTIFRAUD_WEBHOOK_URL") or None,
            antifraud_timeout_seconds=float(
                env.get("ANTIFRAUD_TIMEOUT_SECONDS", defaults.antifraud_timeout_seconds)
            ),
            high_risk_threshold_cents=int(
                env.get("HIGH_RISK_THRESHOLD_CENTS", defaults.high_risk_threshold_cents)
            ),
            fx_rates_to_brl=(
                parse_fx_rates(env["FX_RATES_TO_BRL"])
                if env.get("FX_RATES_TO_BRL")
                else defaults.fx_rates_to_brl
            ),
        )
