"""Unit tests for ``SLSAv1PredicateBuilder`` and ``SLSAProvenancePredicateAssembler``."""

from __future__ import annotations

import dataclasses

import pytest

from hpc_provenance.domain.exceptions import ProvenanceGenerationError
from hpc_provenance.domain.models.provenance import (
    BuildDefinition,
    BuilderIdentity,
    RunDetails,
    SLSAProvenancePredicate,
)
from hpc_provenance.domain.models.provenance_context import ProvenanceContext
from hpc_provenance.domain.models.provenance_metadata import BuildMetadata
from hpc_provenance.infrastructure.provenance.slsa_predicate_builder import (
    SLSA_V1_PREDICATE_TYPE,
    SLSAProvenancePredicateAssembler,
    SLSAv1PredicateBuilder,
)
from hpc_provenance.infrastructure.provenance.slsa_predicate_mapper import (
    build_definition_from_context,
    run_details_from_context,
)


def test_predicate_type() -> None:
    assert SLSAv1PredicateBuilder().predicate_type == "https://slsa.dev/provenance/v1"
    assert SLSA_V1_PREDICATE_TYPE == "https://slsa.dev/provenance/v1"


def test_build_returns_predicate_assembled_from_context(
    sample_provenance_context: ProvenanceContext,
) -> None:
    predicate = SLSAv1PredicateBuilder().build(sample_provenance_context)

    assert predicate == SLSAProvenancePredicate(
        build_definition=build_definition_from_context(sample_provenance_context),
        run_details=run_details_from_context(sample_provenance_context),
    )


def test_build_propagates_mapping_errors_for_unsupported_scheduler(
    sample_provenance_context: ProvenanceContext,
) -> None:
    job_metadata = sample_provenance_context.job_metadata
    unsupported_job_id = dataclasses.replace(job_metadata.job_id, scheduler="pbs")
    context = dataclasses.replace(
        sample_provenance_context,
        job_metadata=dataclasses.replace(job_metadata, job_id=unsupported_job_id),
    )

    with pytest.raises(ProvenanceGenerationError):
        SLSAv1PredicateBuilder().build(context)


# --- SLSAProvenancePredicateAssembler -----------------------------------------


def _build_definition() -> BuildDefinition:
    return BuildDefinition(
        build_type="https://hpc-provenance.dev/build-types/slurm-job/v1",
        external_parameters={},
        internal_parameters={},
    )


def _run_details() -> RunDetails:
    return RunDetails(
        builder=BuilderIdentity(id="https://example.org/hpc-provenance/builder/v1"),
        metadata=BuildMetadata(invocation_id="123456", started_on=None, finished_on=None),
    )


def test_assembler_builds_predicate_from_parts() -> None:
    build_definition = _build_definition()
    run_details = _run_details()

    predicate = (
        SLSAProvenancePredicateAssembler()
        .with_build_definition(build_definition)
        .with_run_details(run_details)
        .build()
    )

    assert predicate == SLSAProvenancePredicate(
        build_definition=build_definition, run_details=run_details
    )


def test_assembler_returns_self_for_chaining() -> None:
    assembler = SLSAProvenancePredicateAssembler()

    assert assembler.with_build_definition(_build_definition()) is assembler
    assert assembler.with_run_details(_run_details()) is assembler


@pytest.mark.parametrize(
    "configure",
    [
        lambda assembler: assembler,
        lambda assembler: assembler.with_build_definition(_build_definition()),
        lambda assembler: assembler.with_run_details(_run_details()),
    ],
)
def test_assembler_rejects_incomplete_predicates(configure) -> None:
    assembler = configure(SLSAProvenancePredicateAssembler())

    with pytest.raises(ProvenanceGenerationError):
        assembler.build()
