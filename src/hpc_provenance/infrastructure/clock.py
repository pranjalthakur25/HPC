"""System clock implementation of the ``Clock`` port."""

from __future__ import annotations

from datetime import datetime, timezone

from hpc_provenance.domain.interfaces.clock import Clock


class SystemClock(Clock):
    """Returns the real, current, timezone-aware UTC time."""

    def now(self) -> datetime:
        """See ``Clock.now``."""
        return datetime.now(timezone.utc)
