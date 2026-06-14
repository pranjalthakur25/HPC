"""Result DTOs for application use cases."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hpc_provenance.domain.interfaces.repositories import ProvenanceRecordId
from hpc_provenance.domain.models.dsse import DSSEEnvelope


@dataclass(frozen=True, slots=True)
class SignProvenanceResult:
    """Output of ``SignProvenanceUseCase``."""

    record_id: ProvenanceRecordId
    envelope: DSSEEnvelope


@dataclass(frozen=True, slots=True)
class SlurmProvenanceResult:
    """Output of ``SlurmProvenanceService.run_epilogue``."""

    statement_path: Path
    envelope_path: Path
    record_id: ProvenanceRecordId
