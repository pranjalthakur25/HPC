"""Use case: verify a stored, signed provenance envelope against a policy."""

from __future__ import annotations

from dataclasses import dataclass

from hpc_provenance.application.dto.requests import VerifyProvenanceRequest
from hpc_provenance.domain.interfaces.repositories import KeyRepository, ProvenanceRepository
from hpc_provenance.domain.interfaces.signing import DSSEEnvelopeVerifier
from hpc_provenance.domain.models.verification import VerificationResult


@dataclass(frozen=True, slots=True)
class VerifyProvenanceUseCase:
    """Loads a stored ``DSSEEnvelope`` and verifies it against a
    ``VerificationPolicy``.

    See ``ARCHITECTURE.md`` section 7.3 for the sequence diagram.
    """

    envelope_verifier: DSSEEnvelopeVerifier
    key_repository: KeyRepository
    provenance_repository: ProvenanceRepository

    def execute(self, request: VerifyProvenanceRequest) -> VerificationResult:
        """Run the verify-provenance flow.

        Steps (not yet implemented):
            1. Load the ``DSSEEnvelope`` via
               ``provenance_repository.get(request.record_id)``.
            2. Resolve verification keys for
               ``request.policy.trusted_key_ids`` via ``key_repository``.
            3. Verify the envelope via ``envelope_verifier.verify``.
            4. Return the resulting ``VerificationResult``.

        Raises:
            ProvenanceRecordNotFoundError: propagated from
                ``provenance_repository``.
            VerificationError: propagated from ``envelope_verifier`` /
                ``key_repository`` if verification cannot be attempted.
        """
        raise NotImplementedError
