"""Ports for building SLSA predicates and in-toto statements."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from hpc_provenance.domain.models.in_toto import InTotoStatement
from hpc_provenance.domain.models.provenance import ResourceDescriptor, SLSAProvenancePredicate
from hpc_provenance.domain.models.provenance_context import ProvenanceContext


@runtime_checkable
class ProvenancePredicateBuilder(Protocol):
    """Builds a SLSA provenance predicate from a ``ProvenanceContext``."""

    @property
    def predicate_type(self) -> str:
        """The in-toto ``predicateType`` URI this builder produces, e.g.
        ``"https://slsa.dev/provenance/v1"``.
        """
        ...

    def build(self, context: ProvenanceContext) -> SLSAProvenancePredicate:
        """Translate collected metadata into a SLSA provenance predicate.

        Raises:
            ProvenanceGenerationError: if ``context`` is missing data
                required to populate the predicate.
        """
        ...


@runtime_checkable
class InTotoStatementBuilder(Protocol):
    """Wraps a predicate and its subjects into an in-toto Statement."""

    def build(
        self,
        subjects: Sequence[ResourceDescriptor],
        predicate_type: str,
        predicate: SLSAProvenancePredicate,
    ) -> InTotoStatement:
        """Serialize ``predicate`` and assemble it with ``subjects`` into a
        Statement.

        Raises:
            ProvenanceGenerationError: if ``predicate`` cannot be serialized.
        """
        ...
