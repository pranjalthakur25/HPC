"""In-memory repository implementations for tests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from uuid import uuid4

from hpc_provenance.domain.exceptions import (
    ProvenanceRecordNotFoundError,
    SigningError,
    VerificationError,
)
from hpc_provenance.domain.interfaces.repositories import (
    KeyRepository,
    ProvenanceQuery,
    ProvenanceRecordId,
    ProvenanceRecordSummary,
    ProvenanceRepository,
)
from hpc_provenance.domain.models.dsse import DSSEEnvelope
from hpc_provenance.domain.value_objects import SigningKey, VerificationKey


class InMemoryProvenanceRepository(ProvenanceRepository):
    """Stores envelopes in a dict.

    Fully implemented -- used as a test double and as a behavioural
    reference for ``FilesystemProvenanceRepository``.
    """

    def __init__(self) -> None:
        self._envelopes: dict[ProvenanceRecordId, DSSEEnvelope] = {}
        self._metadata: dict[ProvenanceRecordId, Mapping[str, str]] = {}
        self._created_at: dict[ProvenanceRecordId, datetime] = {}

    def save(
        self, envelope: DSSEEnvelope, *, metadata: Mapping[str, str] | None = None
    ) -> ProvenanceRecordId:
        record_id = ProvenanceRecordId(value=str(uuid4()))
        self._envelopes[record_id] = envelope
        self._metadata[record_id] = metadata or {}
        self._created_at[record_id] = datetime.now(UTC)
        return record_id

    def get(self, record_id: ProvenanceRecordId) -> DSSEEnvelope:
        try:
            return self._envelopes[record_id]
        except KeyError as exc:
            raise ProvenanceRecordNotFoundError(record_id.value) from exc

    def list(self, query: ProvenanceQuery | None = None) -> Sequence[ProvenanceRecordSummary]:
        return tuple(
            ProvenanceRecordSummary(
                record_id=record_id,
                payload_type=envelope.payload_type,
                created_at=self._created_at[record_id],
                metadata=self._metadata[record_id],
            )
            for record_id, envelope in self._envelopes.items()
        )


class InMemoryKeyRepository(KeyRepository):
    """Returns pre-registered ``SigningKey``/``VerificationKey`` objects.

    Fully implemented -- used as a test double.
    """

    def __init__(
        self,
        signing_keys: Mapping[str, SigningKey] | None = None,
        verification_keys: Mapping[str, VerificationKey] | None = None,
        trusted_key_ids: frozenset[str] | None = None,
    ) -> None:
        self._signing_keys = dict(signing_keys or {})
        self._verification_keys = dict(verification_keys or {})
        self._trusted_key_ids = trusted_key_ids or frozenset(self._verification_keys)

    def get_signing_key(self, key_id: str) -> SigningKey:
        try:
            return self._signing_keys[key_id]
        except KeyError as exc:
            raise SigningError(f"Unknown signing key id: {key_id!r}") from exc

    def get_verification_key(self, key_id: str) -> VerificationKey:
        try:
            return self._verification_keys[key_id]
        except KeyError as exc:
            raise VerificationError(f"Unknown verification key id: {key_id!r}") from exc

    def trusted_key_ids(self) -> frozenset[str]:
        return self._trusted_key_ids
