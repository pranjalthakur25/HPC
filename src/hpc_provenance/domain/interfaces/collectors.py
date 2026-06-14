"""Ports for collecting metadata from external sources."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Protocol, runtime_checkable

from hpc_provenance.domain.enums import ArtifactRole
from hpc_provenance.domain.models.artifact import Artifact
from hpc_provenance.domain.models.git_metadata import GitRepositoryMetadata
from hpc_provenance.domain.models.scheduler_metadata import SlurmJobMetadata
from hpc_provenance.domain.value_objects import JobIdentifier


@runtime_checkable
class GitMetadataCollector(Protocol):
    """Collects git repository metadata for a working tree."""

    def collect(self, repository_path: Path) -> GitRepositoryMetadata:
        """Return metadata for the git repository at ``repository_path``.

        Raises:
            MetadataCollectionError: if ``repository_path`` is not inside a
                git working tree or git metadata cannot be read.
        """
        ...


@runtime_checkable
class SchedulerMetadataCollector(Protocol):
    """Collects HPC scheduler metadata for a job."""

    def collect(self, job_id: JobIdentifier | None = None) -> SlurmJobMetadata:
        """Return metadata for ``job_id``, or the currently-running job if
        ``job_id`` is ``None`` (resolved from the scheduler's environment,
        e.g. ``SLURM_JOB_ID``).

        Raises:
            MetadataCollectionError: if the job cannot be found or scheduler
                metadata cannot be read.
        """
        ...


@runtime_checkable
class ArtifactMetadataCollector(Protocol):
    """Collects digests and metadata for artifact files."""

    def collect(self, paths: Iterable[Path], role: ArtifactRole) -> tuple[Artifact, ...]:
        """Return one ``Artifact`` per path in ``paths``, tagged with ``role``.

        Raises:
            MetadataCollectionError: if a path does not exist or cannot be
                read/hashed.
        """
        ...
