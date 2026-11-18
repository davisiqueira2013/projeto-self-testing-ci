from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

Clock = Callable[[], datetime]
IdFactory = Callable[[], str]


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())
