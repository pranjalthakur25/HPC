"""Domain-level exception hierarchy.

Ports raise these exceptions (never raw third-party exceptions) so that
application and presentation code can depend only on domain types.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain-level errors."""


class MetadataCollectionError(DomainError):
    """Raised when git, scheduler, or artifact metadata cannot be collected."""


class InvalidMetadataError(DomainError):
    """Raised when a domain model is constructed with invalid field values."""


class ProvenanceGenerationError(DomainError):
    """Raised when a SLSA predicate or in-toto statement cannot be built."""


class SigningError(DomainError):
    """Raised when a DSSE envelope cannot be signed."""


class VerificationError(DomainError):
    """Raised when DSSE envelope verification cannot be *attempted*.

    Distinct from a *completed* verification that reports policy failures via
    ``VerificationResult.is_valid is False``.
    """


class ProvenanceRecordNotFoundError(DomainError):
    """Raised when a ``ProvenanceRecordId`` does not exist in a repository."""
