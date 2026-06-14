"""Request DTOs for application use cases."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from hpc_provenance.domain.interfaces.repositories import ProvenanceRecordId
from hpc_provenance.domain.models.in_toto import InTotoStatement
from hpc_provenance.domain.models.verification import VerificationPolicy
from hpc_provenance.domain.value_objects import JobIdentifier


@dataclass(frozen=True, slots=True)
class GenerateProvenanceRequest:
    """Input to ``GenerateProvenanceUseCase``."""

    builder_id: str
    product_paths: tuple[Path, ...]
    material_paths: tuple[Path, ...] = ()
    job_id: JobIdentifier | None = None
    git_repository_path: Path | None = None


@dataclass(frozen=True, slots=True)
class SignProvenanceRequest:
    """Input to ``SignProvenanceUseCase``."""

    statement: InTotoStatement
    signing_key_ids: tuple[str, ...]
    metadata: Mapping[str, str] | None = None


@dataclass(frozen=True, slots=True)
class VerifyProvenanceRequest:
    """Input to ``VerifyProvenanceUseCase``."""

    record_id: ProvenanceRecordId
    policy: VerificationPolicy
