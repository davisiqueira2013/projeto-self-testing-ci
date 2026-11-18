"""Integração com o gateway anti-fraude externo (webhook fictício)."""

from __future__ import annotations

from typing import Protocol

import httpx


class AntiFraudGateway(Protocol):
    def notify_transfer(self, event: dict) -> None: ...


class WebhookAntiFraudGateway:
    """Envia o evento da transferência via HTTP POST para o webhook configurado."""

    def __init__(self, url: str, client: httpx.Client | None = None, timeout: float = 2.0):
        self._url = url
        self._client = client or httpx.Client(timeout=timeout)

    def notify_transfer(self, event: dict) -> None:
        response = self._client.post(
            self._url,
            json=event,
            headers={"X-Event-Type": event.get("event", "unknown")},
        )
        response.raise_for_status()


class NullAntiFraudGateway:
    """Usado quando nenhum webhook está configurado (ex.: teste de carga local)."""

    def notify_transfer(self, event: dict) -> None:
        return None
