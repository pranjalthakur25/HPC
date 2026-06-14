"""Fake provenance-building implementations for tests."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from hpc_provenance.domain.models.in_toto import InTotoStatement
from hpc_provenance.domain.models.provenance import ResourceDescriptor, SLSAProvenancePredicate
from hpc_provenance.domain.models.provenance_context import ProvenanceContext


@dataclass(frozen=True, slots=True)
class FakeProvenancePredicateBuilder:
    """Returns a fixed ``SLSAProvenancePredicate``, ignoring ``context``."""

    result: SLSAProvenancePredicate
    predicate_type_value: str = "https://slsa.dev/provenance/v1"

    @property
    def predicate_type(self) -> str:
        return self.predicate_type_value

    def build(self, context: ProvenanceContext) -> SLSAProvenancePredicate:
        return self.result


@dataclass(frozen=True, slots=True)
class FakeInTotoStatementBuilder:
    """Returns a fixed ``InTotoStatement``, ignoring its inputs."""

    result: InTotoStatement

    def build(
        self,
        subjects: Sequence[ResourceDescriptor],
        predicate_type: str,
        predicate: SLSAProvenancePredicate,
    ) -> InTotoStatement:
        return self.result
