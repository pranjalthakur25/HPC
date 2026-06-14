"""Clock port -- abstracts ``datetime.now()`` for testability."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """Provides the current time."""

    def now(self) -> datetime:
        """Return the current, timezone-aware UTC time."""
        ...
