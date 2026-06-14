"""in-toto Statement v1 builder."""

from __future__ import annotations

from collections.abc import Sequence

from hpc_provenance.domain.interfaces.provenance import InTotoStatementBuilder
from hpc_provenance.domain.models.in_toto import InTotoStatement
from hpc_provenance.domain.models.provenance import ResourceDescriptor, SLSAProvenancePredicate
from hpc_provenance.infrastructure.provenance.slsa_predicate_mapper import predicate_to_dict


class InTotoV1StatementBuilder(InTotoStatementBuilder):
    """Serializes a ``SLSAProvenancePredicate`` into ``predicate`` and
    assembles an ``InTotoStatement`` with the given ``subjects``.
    """

    def build(
        self,
        subjects: Sequence[ResourceDescriptor],
        predicate_type: str,
        predicate: SLSAProvenancePredicate,
    ) -> InTotoStatement:
        """See ``InTotoStatementBuilder.build``.

        ``predicate`` is converted to its SLSA v1 ``predicate`` JSON shape
        (via ``slsa_predicate_mapper.predicate_to_dict``) and combined with
        ``predicate_type`` and ``subjects`` into an ``InTotoStatement``.
        ``subjects`` map 1:1 to ``InTotoStatement.subjects``.
        """
        return InTotoStatement(
            subjects=tuple(subjects),
            predicate_type=predicate_type,
            predicate=predicate_to_dict(predicate),
        )
