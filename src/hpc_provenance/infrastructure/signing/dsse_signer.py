"""DSSE envelope signer: signs an in-toto Statement with RSA / ECDSA keys."""

from __future__ import annotations

from collections.abc import Sequence

from hpc_provenance.domain.exceptions import SigningError
from hpc_provenance.domain.interfaces.signing import DSSEEnvelopeSigner, PayloadSigner
from hpc_provenance.domain.models.dsse import DSSEEnvelope, DSSESignature
from hpc_provenance.domain.models.in_toto import InTotoStatement
from hpc_provenance.infrastructure.signing.dsse_envelope_builder import DsseEnvelopeBuilder


class DsseSigner(DSSEEnvelopeSigner):
    """Builds the DSSE Pre-Authentication Encoding (PAE) for an in-toto
    Statement and signs it with one or more ``PayloadSigner``s (RSA or
    ECDSA).
    """

    def __init__(self, envelope_builder: DsseEnvelopeBuilder | None = None) -> None:
        self._envelope_builder = envelope_builder or DsseEnvelopeBuilder()

    def sign(self, statement: InTotoStatement, signers: Sequence[PayloadSigner]) -> DSSEEnvelope:
        if not signers:
            raise SigningError("At least one signer is required to sign a DSSE envelope")

        payload = self._envelope_builder.encode_payload(statement)
        pae = DsseEnvelopeBuilder.pae(self._envelope_builder.payload_type, payload)

        signatures: list[DSSESignature] = []
        for signer in signers:
            try:
                signature_bytes = signer.sign(pae)
            except SigningError:
                raise
            except Exception as exc:
                raise SigningError(f"Signing with key {signer.key_id!r} failed: {exc}") from exc
            signatures.append(DSSESignature(key_id=signer.key_id, signature=signature_bytes))

        return DSSEEnvelope(
            payload=payload,
            payload_type=self._envelope_builder.payload_type,
            signatures=tuple(signatures),
        )
