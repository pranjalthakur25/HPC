"""Ports for the Observer Agent: discovering recently-finished jobs, loading
their declared build definition (``JobManifest``), and tracking which jobs
have already been processed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from hpc_provenance.domain.models.observer import JobManifest
from hpc_provenance.domain.models.scheduler_metadata import SlurmJobMetadata


@dataclass(frozen=True, slots=True)
class ObserverState:
    """Tracks Observer progress across polls."""

    processed_job_ids: frozenset[str]
    last_poll_at: datetime | None


@runtime_checkable
class JobDiscoverySource(Protocol):
    """Lists jobs the Observer should consider, regardless of state."""

    def list_recent_jobs(
        self, *, user: str, since: datetime | None = None
    ) -> tuple[SlurmJobMetadata, ...]:
        """Return metadata for jobs belonging to ``user`` that were active or
        finished at or after ``since`` (or a scheduler-defined default
        window if ``since`` is ``None``).

        May include jobs in any state; the caller is responsible for
        filtering to terminal states.

        Raises:
            MetadataCollectionError: if the underlying scheduler query fails.
        """
        ...


@runtime_checkable
class JobManifestRepository(Protocol):
    """Loads a job's declared build definition."""

    def load(self, working_directory: Path) -> JobManifest | None:
        """Return the ``JobManifest`` declared for ``working_directory``, or
        ``None`` if no manifest file is present.
        """
        ...


@runtime_checkable
class ObserverStateRepository(Protocol):
    """Persists ``ObserverState`` between polls."""

    def load(self) -> ObserverState:
        """Return the last-saved ``ObserverState``, or an empty/initial
        state if none has been saved yet.
        """
        ...

    def save(self, state: ObserverState) -> None:
        """Persist ``state``, overwriting any previously-saved state."""
        ...
