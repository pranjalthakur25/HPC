"""Unit tests for ``SlsaPredicateGenerator``."""

from __future__ import annotations

import json
from pathlib import Path

from hpc_provenance.domain.models.provenance import (
    BuildDefinition,
    BuilderIdentity,
    RunDetails,
    SLSAProvenancePredicate,
)
from hpc_provenance.domain.models.provenance_context import ProvenanceContext
from hpc_provenance.domain.models.provenance_metadata import BuildMetadata
from hpc_provenance.infrastructure.provenance.slsa_predicate_builder import SLSAv1PredicateBuilder
from hpc_provenance.infrastructure.provenance.slsa_predicate_generator import SlsaPredicateGenerator
from hpc_provenance.infrastructure.provenance.slsa_predicate_mapper import predicate_to_dict
from tests.fakes.provenance import FakeProvenancePredicateBuilder


def _fake_predicate() -> SLSAProvenancePredicate:
    return SLSAProvenancePredicate(
        build_definition=BuildDefinition(
            build_type="https://hpc-provenance.dev/build-types/slurm-job/v1",
            external_parameters={},
            internal_parameters={},
        ),
        run_details=RunDetails(
            builder=BuilderIdentity(id="https://example.org/hpc-provenance/builder/v1"),
            metadata=BuildMetadata(invocation_id="123456", started_on=None, finished_on=None),
        ),
    )


def test_default_predicate_type_is_slsa_v1() -> None:
    generator = SlsaPredicateGenerator()

    assert generator.predicate_type == "https://slsa.dev/provenance/v1"


def test_generate_delegates_to_default_builder(sample_provenance_context: ProvenanceContext) -> None:
    generator = SlsaPredicateGenerator()

    predicate = generator.generate(sample_provenance_context)

    assert predicate == SLSAv1PredicateBuilder().build(sample_provenance_context)


def test_generate_uses_injected_predicate_builder(sample_provenance_context: ProvenanceContext) -> None:
    fake_predicate = _fake_predicate()
    generator = SlsaPredicateGenerator(
        predicate_builder=FakeProvenancePredicateBuilder(result=fake_predicate)
    )

    assert generator.generate(sample_provenance_context) == fake_predicate
    assert generator.predicate_type == "https://slsa.dev/provenance/v1"


def test_to_dict_matches_mapper(sample_provenance_context: ProvenanceContext) -> None:
    generator = SlsaPredicateGenerator()
    predicate = generator.generate(sample_provenance_context)

    assert generator.to_dict(predicate) == predicate_to_dict(predicate)


def test_to_json_round_trips_to_dict(sample_provenance_context: ProvenanceContext) -> None:
    generator = SlsaPredicateGenerator()
    predicate = generator.generate(sample_provenance_context)

    assert json.loads(generator.to_json(predicate)) == generator.to_dict(predicate)


def test_to_dict_matches_slsa_v1_predicate_shape(sample_provenance_context: ProvenanceContext) -> None:
    generator = SlsaPredicateGenerator()
    predicate = generator.generate(sample_provenance_context)

    result = generator.to_dict(predicate)

    assert set(result) == {"buildDefinition", "runDetails"}
    build_definition = result["buildDefinition"]
    assert {"buildType", "externalParameters", "internalParameters", "resolvedDependencies"} <= set(
        build_definition
    )
    run_details = result["runDetails"]
    assert {"builder", "metadata"} <= set(run_details)
    assert run_details["builder"] == {"id": sample_provenance_context.builder_id}


def test_write_predicate_writes_predicate_json(
    tmp_path: Path, sample_provenance_context: ProvenanceContext
) -> None:
    generator = SlsaPredicateGenerator()
    predicate = generator.generate(sample_provenance_context)
    output_path = tmp_path / "predicate.json"

    returned_path = generator.write_predicate(predicate, output_path)

    assert returned_path == output_path
    assert json.loads(output_path.read_text(encoding="utf-8")) == generator.to_dict(predicate)


def test_generate_predicate_file_generates_and_writes(
    tmp_path: Path, sample_provenance_context: ProvenanceContext
) -> None:
    generator = SlsaPredicateGenerator()
    output_path = tmp_path / "predicate.json"

    returned_path = generator.generate_predicate_file(sample_provenance_context, output_path)

    assert returned_path == output_path
    on_disk = json.loads(output_path.read_text(encoding="utf-8"))
    assert on_disk == generator.to_dict(generator.generate(sample_provenance_context))
