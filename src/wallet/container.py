"""Composition root: monta as dependências a partir das configurações."""

from __future__ import annotations

from dataclasses import dataclass

from wallet.config import Settings
from wallet.gateways.antifraud import (
    AntiFraudGateway,
    NullAntiFraudGateway,
    WebhookAntiFraudGateway,
)
from wallet.gateways.fx import ExchangeRateProvider, StaticExchangeRateProvider
from wallet.gateways.kyc import CpfKycProvider, KycProvider
from wallet.repositories.sqlite import SqliteWalletRepository
from wallet.services.account_service import AccountService
from wallet.services.statement_service import StatementService
from wallet.services.transfer_service import TransferService


@dataclass
class Container:
    repository: SqliteWalletRepository
    accounts: AccountService
    transfers: TransferService
    statements: StatementService


def build_container(
    settings: Settings,
    *,
    antifraud: AntiFraudGateway | None = None,
    kyc: KycProvider | None = None,
    fx: ExchangeRateProvider | None = None,
) -> Container:
    repository = SqliteWalletRepository(settings.database_path)
    if antifraud is None:
        antifraud = (
            WebhookAntiFraudGateway(
                settings.antifraud_webhook_url, timeout=settings.antifraud_timeout_seconds
            )
            if settings.antifraud_webhook_url
            else NullAntiFraudGateway()
        )
    return Container(
        repository=repository,
        accounts=AccountService(repository, kyc or CpfKycProvider()),
        transfers=TransferService(
            repository,
            antifraud,
            fx or StaticExchangeRateProvider(settings.fx_rates_to_brl),
            high_risk_threshold_cents=settings.high_risk_threshold_cents,
        ),
        statements=StatementService(repository),
    )
