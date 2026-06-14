"""Fake DSSE signing/verification implementations for tests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from hpc_provenance.domain.interfaces.signing import PayloadSigner
from hpc_provenance.domain.models.dsse import DSSEEnvelope
from hpc_provenance.domain.models.in_toto import InTotoStatement
from hpc_provenance.domain.models.verification import VerificationPolicy, VerificationResult
from hpc_provenance.domain.value_objects import VerificationKey


@dataclass(frozen=True, slots=True)
class FakePayloadSigner:
    """A ``PayloadSigner`` that returns a fixed signature."""

    key_id_value: str
    signature: bytes

    @property
    def key_id(self) -> str:
        return self.key_id_value

    def sign(self, payload: bytes) -> bytes:
        return self.signature


@dataclass(frozen=True, slots=True)
class FakeDSSEEnvelopeSigner:
    """Returns a fixed ``DSSEEnvelope``, ignoring its inputs."""

    result: DSSEEnvelope

    def sign(self, statement: InTotoStatement, signers: Sequence[PayloadSigner]) -> DSSEEnvelope:
        return self.result


@dataclass(frozen=True, slots=True)
class FakeDSSEEnvelopeVerifier:
    """Returns a fixed ``VerificationResult``, ignoring its inputs."""

    result: VerificationResult

    def verify(
        self,
        envelope: DSSEEnvelope,
        policy: VerificationPolicy,
        verification_keys: Mapping[str, VerificationKey],
    ) -> VerificationResult:
        return self.result
