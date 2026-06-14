"""Domain model for build inputs/outputs (materials, products, byproducts)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from hpc_provenance.domain.enums import ArtifactRole
from hpc_provenance.domain.value_objects import Digest


@dataclass(frozen=True, slots=True)
class Artifact:
    """A file (or other addressable resource) involved in a build.

    Converted to a ``ResourceDescriptor`` when included in a SLSA predicate
    or in-toto statement.
    """

    name: str
    uri: str
    digest: Digest
    media_type: str | None
    size_bytes: int | None
    role: ArtifactRole
    created_at: datetime | None = None
