"""Unit tests for ``SystemClock``."""

from __future__ import annotations

from datetime import datetime, timezone

from hpc_provenance.infrastructure.clock import SystemClock


def test_now_returns_timezone_aware_utc_datetime() -> None:
    clock = SystemClock()

    before = datetime.now(timezone.utc)
    now = clock.now()
    after = datetime.now(timezone.utc)

    assert now.tzinfo is not None
    assert now.utcoffset() == timezone.utc.utcoffset(now)
    assert before <= now <= after
