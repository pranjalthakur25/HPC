"""Unit tests for ``InTotoStatementGenerator``."""

from __future__ import annotations

import json
from pathlib import Path

from hpc_provenance.domain.models.in_toto import IN_TOTO_STATEMENT_TYPE, InTotoStatement
from hpc_provenance.domain.models.provenance import ResourceDescriptor, SLSAProvenancePredicate
from hpc_provenance.domain.models.provenance_context import ProvenanceContext
from hpc_provenance.infrastructure.provenance.in_toto_statement_builder import InTotoV1StatementBuilder
from hpc_provenance.infrastructure.provenance.in_toto_statement_generator import InTotoStatementGenerator
from hpc_provenance.infrastructure.provenance.slsa_predicate_builder import (
    SLSA_V1_PREDICATE_TYPE,
    SLSAv1PredicateBuilder,
)
from hpc_provenance.infrastructure.provenance.slsa_predicate_mapper import (
    predicate_to_dict,
    resource_descriptor_from_artifact,
)
from tests.fakes.provenance import FakeInTotoStatementBuilder


def _predicate_and_subjects(
    context: ProvenanceContext,
) -> tuple[SLSAProvenancePredicate, tuple[ResourceDescriptor, ...]]:
    predicate = SLSAv1PredicateBuilder().build(context)
    subjects = tuple(resource_descriptor_from_artifact(product) for product in context.products)
    return predicate, subjects


def test_generate_delegates_to_default_builder(sample_provenance_context: ProvenanceContext) -> None:
    generator = InTotoStatementGenerator()
    predicate, subjects = _predicate_and_subjects(sample_provenance_context)

    statement = generator.generate(subjects, SLSA_V1_PREDICATE_TYPE, predicate)

    assert statement == InTotoV1StatementBuilder().build(subjects, SLSA_V1_PREDICATE_TYPE, predicate)


def test_generate_uses_injected_statement_builder(sample_provenance_context: ProvenanceContext) -> None:
    predicate, subjects = _predicate_and_subjects(sample_provenance_context)
    fake_statement = InTotoStatement(
        subjects=(),
        predicate_type="https://example.org/fake-predicate/v1",
        predicate={},
    )
    generator = InTotoStatementGenerator(
        statement_builder=FakeInTotoStatementBuilder(result=fake_statement)
    )

    assert generator.generate(subjects, SLSA_V1_PREDICATE_TYPE, predicate) == fake_statement


def test_to_dict_matches_statement_to_dict(sample_provenance_context: ProvenanceContext) -> None:
    generator = InTotoStatementGenerator()
    predicate, subjects = _predicate_and_subjects(sample_provenance_context)
    statement = generator.generate(subjects, SLSA_V1_PREDICATE_TYPE, predicate)

    assert generator.to_dict(statement) == statement.to_dict()


def test_to_json_round_trips_to_dict(sample_provenance_context: ProvenanceContext) -> None:
    generator = InTotoStatementGenerator()
    predicate, subjects = _predicate_and_subjects(sample_provenance_context)
    statement = generator.generate(subjects, SLSA_V1_PREDICATE_TYPE, predicate)

    assert json.loads(generator.to_json(statement)) == generator.to_dict(statement)


def test_to_dict_matches_in_toto_statement_v1_shape(sample_provenance_context: ProvenanceContext) -> None:
    generator = InTotoStatementGenerator()
    predicate, subjects = _predicate_and_subjects(sample_provenance_context)
    statement = generator.generate(subjects, SLSA_V1_PREDICATE_TYPE, predicate)

    result = generator.to_dict(statement)

    assert set(result) == {"_type", "subject", "predicateType", "predicate"}
    assert result["_type"] == IN_TOTO_STATEMENT_TYPE
    assert result["predicateType"] == SLSA_V1_PREDICATE_TYPE
    assert result["predicate"] == predicate_to_dict(predicate)
    assert result["subject"] == [descriptor.to_dict() for descriptor in subjects]


def test_write_statement_writes_statement_json(
    tmp_path: Path, sample_provenance_context: ProvenanceContext
) -> None:
    generator = InTotoStatementGenerator()
    predicate, subjects = _predicate_and_subjects(sample_provenance_context)
    statement = generator.generate(subjects, SLSA_V1_PREDICATE_TYPE, predicate)
    output_path = tmp_path / "statement.json"

    returned_path = generator.write_statement(statement, output_path)

    assert returned_path == output_path
    assert json.loads(output_path.read_text(encoding="utf-8")) == generator.to_dict(statement)


def test_generate_statement_file_generates_and_writes(
    tmp_path: Path, sample_provenance_context: ProvenanceContext
) -> None:
    generator = InTotoStatementGenerator()
    predicate, subjects = _predicate_and_subjects(sample_provenance_context)
    output_path = tmp_path / "statement.json"

    returned_path = generator.generate_statement_file(subjects, SLSA_V1_PREDICATE_TYPE, predicate, output_path)

    assert returned_path == output_path
    on_disk = json.loads(output_path.read_text(encoding="utf-8"))
    assert on_disk == generator.to_dict(generator.generate(subjects, SLSA_V1_PREDICATE_TYPE, predicate))
