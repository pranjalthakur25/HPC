"""Ports for DSSE signing and verification."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol, runtime_checkable

from hpc_provenance.domain.models.dsse import DSSEEnvelope
from hpc_provenance.domain.models.in_toto import InTotoStatement
from hpc_provenance.domain.models.verification import VerificationPolicy, VerificationResult
from hpc_provenance.domain.value_objects import VerificationKey


@runtime_checkable
class PayloadSigner(Protocol):
    """Signs raw bytes with a single key. Used by ``DSSEEnvelopeSigner``."""

    @property
    def key_id(self) -> str:
        """The identifier of the key this signer uses, surfaced in
        ``DSSESignature.key_id``.
        """
        ...

    def sign(self, payload: bytes) -> bytes:
        """Return the raw signature bytes over ``payload``.

        Raises:
            SigningError: if signing fails (e.g. key unavailable).
        """
        ...


@runtime_checkable
class DSSEEnvelopeSigner(Protocol):
    """Produces a ``DSSEEnvelope`` for an in-toto Statement."""

    def sign(self, statement: InTotoStatement, signers: Sequence[PayloadSigner]) -> DSSEEnvelope:
        """PAE-encode ``statement`` and sign it with each of ``signers``,
        producing one ``DSSESignature`` per signer.

        Raises:
            SigningError: if encoding or any signature fails.
        """
        ...


@runtime_checkable
class DSSEEnvelopeVerifier(Protocol):
    """Verifies a ``DSSEEnvelope`` against a ``VerificationPolicy``."""

    def verify(
        self,
        envelope: DSSEEnvelope,
        policy: VerificationPolicy,
        verification_keys: Mapping[str, VerificationKey],
    ) -> VerificationResult:
        """Check ``envelope``'s signatures against ``verification_keys`` and
        its payload against ``policy``.

        Raises:
            VerificationError: if verification cannot be *attempted* (e.g.
                malformed envelope) -- as opposed to a *completed*
                verification that found policy violations, which is reported
                via ``VerificationResult.is_valid is False``.
        """
        ...
