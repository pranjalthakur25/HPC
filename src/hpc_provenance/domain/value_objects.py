"""Domain value objects: small, immutable data types shared across models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from hpc_provenance.domain.enums import DigestAlgorithm, SchedulerType

type ResourceURI = str
"""A URI identifying a resource (artifact, repository, builder, ...).

Kept as a semantic alias rather than a wrapper type so it interops directly
with in-toto/SLSA JSON, which represents URIs as plain strings.
"""


@dataclass(frozen=True, slots=True)
class Digest:
    """A single cryptographic digest of some content."""

    algorithm: DigestAlgorithm
    hex_value: str

    def as_digest_set(self) -> Mapping[str, str]:
        """Return this digest in in-toto's ``DigestSet`` shape (``{algo: hex}``)."""
        return {self.algorithm.value: self.hex_value}

    def __str__(self) -> str:
        return f"{self.algorithm.value}:{self.hex_value}"


@dataclass(frozen=True, slots=True)
class JobIdentifier:
    """Identifies a single job (or array task) within a scheduler."""

    scheduler: SchedulerType
    value: str
    array_index: str | None = None

    def __str__(self) -> str:
        if self.array_index is None:
            return f"{self.scheduler.value}:{self.value}"
        return f"{self.scheduler.value}:{self.value}_{self.array_index}"


@dataclass(frozen=True, slots=True)
class SigningKey:
    """Opaque private key material plus identifying metadata.

    The byte format of ``private_key_material`` is adapter-defined (e.g. PEM)
    and interpreted only by the ``DSSEEnvelopeSigner`` implementation that
    consumes it.
    """

    key_id: str
    algorithm: str
    private_key_material: bytes


@dataclass(frozen=True, slots=True)
class VerificationKey:
    """Opaque public key material plus identifying metadata."""

    key_id: str
    algorithm: str
    public_key_material: bytes
