"""Validação cadastral (KYC) do titular da conta."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from wallet.domain.rules import is_valid_cpf


@dataclass(frozen=True)
class KycResult:
    approved: bool
    reason: str = ""


class KycProvider(Protocol):
    def validate(self, holder_name: str, document: str) -> KycResult: ...


class CpfKycProvider:
    """Implementação local: nome mínimo e CPF com dígitos verificadores válidos."""

    def validate(self, holder_name: str, document: str) -> KycResult:
        if len((holder_name or "").strip()) < 3:
            return KycResult(False, "holder name must have at least 3 characters")
        if not is_valid_cpf(document):
            return KycResult(False, "invalid CPF")
        return KycResult(True)
