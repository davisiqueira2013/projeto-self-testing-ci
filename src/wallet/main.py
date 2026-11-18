"""Ponto de entrada ASGI: ``uvicorn wallet.main:app``."""

from wallet.controllers.api import create_app

app = create_app()
