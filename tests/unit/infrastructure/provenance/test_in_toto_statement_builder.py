"""Unit tests for ``InTotoV1StatementBuilder``."""

from __future__ import annotations

from hpc_provenance.domain.models.in_toto import IN_TOTO_STATEMENT_TYPE, InTotoStatement
from hpc_provenance.domain.models.provenance_context import ProvenanceContext
from hpc_provenance.infrastructure.provenance.in_toto_statement_builder import InTotoV1StatementBuilder
from hpc_provenance.infrastructure.provenance.slsa_predicate_builder import (
    SLSA_V1_PREDICATE_TYPE,
    SLSAv1PredicateBuilder,
)
from hpc_provenance.infrastructure.provenance.slsa_predicate_mapper import (
    predicate_to_dict,
    resource_descriptor_from_artifact,
)


def test_build_wraps_predicate_and_subjects(sample_provenance_context: ProvenanceContext) -> None:
    predicate = SLSAv1PredicateBuilder().build(sample_provenance_context)
    subjects = tuple(
        resource_descriptor_from_artifact(product) for product in sample_provenance_context.products
    )

    statement = InTotoV1StatementBuilder().build(subjects, SLSA_V1_PREDICATE_TYPE, predicate)

    assert statement == InTotoStatement(
        subjects=subjects,
        predicate_type=SLSA_V1_PREDICATE_TYPE,
        predicate=predicate_to_dict(predicate),
    )


def test_build_sets_default_in_toto_statement_type(
    sample_provenance_context: ProvenanceContext,
) -> None:
    predicate = SLSAv1PredicateBuilder().build(sample_provenance_context)

    statement = InTotoV1StatementBuilder().build((), SLSA_V1_PREDICATE_TYPE, predicate)

    assert statement.type_ == IN_TOTO_STATEMENT_TYPE
    assert statement.predicate_type == SLSA_V1_PREDICATE_TYPE


def test_build_serializes_predicate_to_slsa_v1_shape(
    sample_provenance_context: ProvenanceContext,
) -> None:
    predicate = SLSAv1PredicateBuilder().build(sample_provenance_context)

    statement = InTotoV1StatementBuilder().build((), SLSA_V1_PREDICATE_TYPE, predicate)

    assert set(statement.predicate) == {"buildDefinition", "runDetails"}


def test_build_to_dict_matches_in_toto_statement_v1_shape(
    sample_provenance_context: ProvenanceContext,
) -> None:
    predicate = SLSAv1PredicateBuilder().build(sample_provenance_context)
    subjects = tuple(
        resource_descriptor_from_artifact(product) for product in sample_provenance_context.products
    )

    statement = InTotoV1StatementBuilder().build(subjects, SLSA_V1_PREDICATE_TYPE, predicate)
    result = statement.to_dict()

    assert set(result) == {"_type", "subject", "predicateType", "predicate"}
    assert result["_type"] == "https://in-toto.io/Statement/v1"
    assert result["predicateType"] == SLSA_V1_PREDICATE_TYPE
    assert result["subject"] == [descriptor.to_dict() for descriptor in subjects]
