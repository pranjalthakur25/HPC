"""Domain models for provenance verification results and policy."""

from __future__ import annotations

from dataclasses import dataclass

from hpc_provenance.domain.enums import IssueSeverity


@dataclass(frozen=True, slots=True)
class VerificationIssue:
    """A single finding from a verification run."""

    code: str
    message: str
    severity: IssueSeverity


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """The outcome of verifying a ``DSSEEnvelope`` against a ``VerificationPolicy``."""

    is_valid: bool
    issues: tuple[VerificationIssue, ...]
    verified_key_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class VerificationPolicy:
    """The rules a ``DSSEEnvelopeVerifier`` checks an envelope against."""

    trusted_key_ids: frozenset[str]
    expected_builder_id: str | None = None
    expected_source_repo_uri: str | None = None
    required_predicate_type: str | None = None
