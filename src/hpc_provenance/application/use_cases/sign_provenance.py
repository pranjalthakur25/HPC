"""Use case: sign an in-toto Statement and persist the resulting envelope."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from hpc_provenance.application.dto.requests import SignProvenanceRequest
from hpc_provenance.application.dto.results import SignProvenanceResult
from hpc_provenance.domain.interfaces.repositories import KeyRepository, ProvenanceRepository
from hpc_provenance.domain.interfaces.signing import DSSEEnvelopeSigner, PayloadSigner
from hpc_provenance.domain.value_objects import SigningKey


@dataclass(frozen=True, slots=True)
class SignProvenanceUseCase:
    """Wraps an ``InTotoStatement`` in a signed ``DSSEEnvelope`` and stores
    it via ``provenance_repository``.

    See ``ARCHITECTURE.md`` section 7.2 for the sequence diagram.
    """

    envelope_signer: DSSEEnvelopeSigner
    key_repository: KeyRepository
    provenance_repository: ProvenanceRepository
    payload_signer_factory: Callable[[SigningKey], PayloadSigner]

    def execute(self, request: SignProvenanceRequest) -> SignProvenanceResult:
        """Run the sign-provenance flow.

        Steps:
            1. Resolve each id in ``request.signing_key_ids`` to a
               ``SigningKey`` via ``key_repository`` and wrap each in a
               ``PayloadSigner`` adapter via ``payload_signer_factory``.
            2. Sign ``request.statement`` via ``envelope_signer``.
            3. Persist the resulting ``DSSEEnvelope`` via
               ``provenance_repository.save``, passing ``request.metadata``.
            4. Return the ``ProvenanceRecordId`` and envelope as a
               ``SignProvenanceResult``.

        Raises:
            SigningError: propagated from ``key_repository`` /
                ``envelope_signer``.
        """
        signers = [
            self.payload_signer_factory(self.key_repository.get_signing_key(key_id))
            for key_id in request.signing_key_ids
        ]
        envelope = self.envelope_signer.sign(request.statement, signers)
        record_id = self.provenance_repository.save(envelope, metadata=request.metadata)
        return SignProvenanceResult(record_id=record_id, envelope=envelope)
