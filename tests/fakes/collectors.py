"""Fake ``*MetadataCollector`` implementations for tests."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from hpc_provenance.domain.enums import ArtifactRole
from hpc_provenance.domain.models.artifact import Artifact
from hpc_provenance.domain.models.git_metadata import GitRepositoryMetadata
from hpc_provenance.domain.models.scheduler_metadata import SlurmJobMetadata
from hpc_provenance.domain.value_objects import JobIdentifier


@dataclass(frozen=True, slots=True)
class FakeGitMetadataCollector:
    """Returns a fixed ``GitRepositoryMetadata`` regardless of input."""

    result: GitRepositoryMetadata

    def collect(self, repository_path: Path) -> GitRepositoryMetadata:
        return self.result


@dataclass(frozen=True, slots=True)
class FakeSchedulerMetadataCollector:
    """Returns a fixed ``SlurmJobMetadata`` regardless of input."""

    result: SlurmJobMetadata

    def collect(self, job_id: JobIdentifier | None = None) -> SlurmJobMetadata:
        return self.result


@dataclass(frozen=True, slots=True)
class FakeArtifactMetadataCollector:
    """Returns a fixed tuple of ``Artifact`` regardless of input.

    Tests should construct ``result`` with the desired ``role``s already
    set, since this fake ignores the ``role`` argument.
    """

    result: tuple[Artifact, ...]

    def collect(self, paths: Iterable[Path], role: ArtifactRole) -> tuple[Artifact, ...]:
        return self.result
