"""SLSA Provenance v1 predicate builder."""

from __future__ import annotations

from hpc_provenance.domain.exceptions import ProvenanceGenerationError
from hpc_provenance.domain.interfaces.provenance import ProvenancePredicateBuilder
from hpc_provenance.domain.models.provenance import (
    BuildDefinition,
    RunDetails,
    SLSAProvenancePredicate,
)
from hpc_provenance.domain.models.provenance_context import ProvenanceContext
from hpc_provenance.infrastructure.provenance.slsa_predicate_mapper import (
    build_definition_from_context,
    run_details_from_context,
)

SLSA_V1_PREDICATE_TYPE = "https://slsa.dev/provenance/v1"


class SLSAProvenancePredicateAssembler:
    """Step-by-step (GoF Builder) assembler for ``SLSAProvenancePredicate``.

    Separated from ``SLSAv1PredicateBuilder`` so the *assembly* of a
    predicate from its parts (``BuildDefinition`` + ``RunDetails``) is
    reusable independently of *how* those parts were derived (e.g. from a
    ``ProvenanceContext``, or supplied directly in a test).
    """

    def __init__(self) -> None:
        self._build_definition: BuildDefinition | None = None
        self._run_details: RunDetails | None = None

    def with_build_definition(self, build_definition: BuildDefinition) -> SLSAProvenancePredicateAssembler:
        self._build_definition = build_definition
        return self

    def with_run_details(self, run_details: RunDetails) -> SLSAProvenancePredicateAssembler:
        self._run_details = run_details
        return self

    def build(self) -> SLSAProvenancePredicate:
        if self._build_definition is None or self._run_details is None:
            raise ProvenanceGenerationError(
                "SLSAProvenancePredicate requires both a build definition and run details"
            )
        return SLSAProvenancePredicate(
            build_definition=self._build_definition,
            run_details=self._run_details,
        )


class SLSAv1PredicateBuilder(ProvenancePredicateBuilder):
    """Builds a SLSA Provenance v1 ``predicate`` from a ``ProvenanceContext``.

    The actual context-to-predicate mapping lives in
    ``infrastructure.provenance.slsa_predicate_mapper`` (kept separate from
    both this builder and the ``domain.models.provenance`` dataclasses);
    this class only orchestrates that mapping and the final assembly via
    ``SLSAProvenancePredicateAssembler``.
    """

    @property
    def predicate_type(self) -> str:
        return SLSA_V1_PREDICATE_TYPE

    def build(self, context: ProvenanceContext) -> SLSAProvenancePredicate:
        """See ``ProvenancePredicateBuilder.build``.

        Raises:
            ProvenanceGenerationError: if ``context.job_metadata`` uses a
                scheduler with no registered SLSA mapping (see
                ``slsa_predicate_mapper``).
        """
        build_definition = build_definition_from_context(context)
        run_details = run_details_from_context(context)

        return (
            SLSAProvenancePredicateAssembler()
            .with_build_definition(build_definition)
            .with_run_details(run_details)
            .build()
        )
