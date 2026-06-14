"""Aggregate input model passed to a ``ProvenancePredicateBuilder``."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from hpc_provenance.domain.models.artifact import Artifact
from hpc_provenance.domain.models.git_metadata import GitRepositoryMetadata
from hpc_provenance.domain.models.scheduler_metadata import SlurmJobMetadata


@dataclass(frozen=True, slots=True)
class ProvenanceContext:
    """Everything collected about a job, assembled by
    ``GenerateProvenanceUseCase`` before being handed to a
    ``ProvenancePredicateBuilder``.
    """

    job_metadata: SlurmJobMetadata
    materials: tuple[Artifact, ...]
    products: tuple[Artifact, ...]
    builder_id: str
    invocation_id: str
    started_at: datetime
    git_metadata: GitRepositoryMetadata | None = None
    finished_at: datetime | None = None
