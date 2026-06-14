"""Repository ports for persisting provenance envelopes and managing keys."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from hpc_provenance.domain.models.dsse import DSSEEnvelope
from hpc_provenance.domain.value_objects import SigningKey, VerificationKey


@dataclass(frozen=True, slots=True)
class ProvenanceRecordId:
    """Opaque identifier for a stored ``DSSEEnvelope``."""

    value: str


@dataclass(frozen=True, slots=True)
class ProvenanceQuery:
    """Filters for ``ProvenanceRepository.list``.

    All fields are optional and combined with AND semantics.
    """

    job_id: str | None = None
    subject_digest: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None


@dataclass(frozen=True, slots=True)
class ProvenanceRecordSummary:
    """Lightweight metadata about a stored envelope, returned by ``list``
    without loading the full envelope.
    """

    record_id: ProvenanceRecordId
    payload_type: str
    created_at: datetime
    metadata: Mapping[str, str]


@runtime_checkable
class ProvenanceRepository(Protocol):
    """Persists and retrieves signed provenance envelopes."""

    def save(
        self, envelope: DSSEEnvelope, *, metadata: Mapping[str, str] | None = None
    ) -> ProvenanceRecordId:
        """Persist ``envelope`` (with optional indexable ``metadata``) and
        return its assigned identifier.
        """
        ...

    def get(self, record_id: ProvenanceRecordId) -> DSSEEnvelope:
        """Return the envelope stored as ``record_id``.

        Raises:
            ProvenanceRecordNotFoundError: if no such record exists.
        """
        ...

    def list(self, query: ProvenanceQuery | None = None) -> Sequence[ProvenanceRecordSummary]:
        """Return summaries of stored records matching ``query`` (or all
        records if ``query`` is ``None``).
        """
        ...


@runtime_checkable
class KeyRepository(Protocol):
    """Provides signing and verification keys."""

    def get_signing_key(self, key_id: str) -> SigningKey:
        """Return the private key identified by ``key_id``.

        Raises:
            SigningError: if ``key_id`` is unknown or unreadable.
        """
        ...

    def get_verification_key(self, key_id: str) -> VerificationKey:
        """Return the public key identified by ``key_id``.

        Raises:
            VerificationError: if ``key_id`` is unknown or unreadable.
        """
        ...

    def trusted_key_ids(self) -> frozenset[str]:
        """Return the set of key ids considered trusted for verification."""
        ...
