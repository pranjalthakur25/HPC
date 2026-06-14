"""Fake ``Clock`` implementation for tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class FixedClock:
    """A ``Clock`` that always returns the same, injected time."""

    fixed_time: datetime

    def now(self) -> datetime:
        return self.fixed_time
