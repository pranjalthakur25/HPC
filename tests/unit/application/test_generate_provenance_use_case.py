"""Unit tests for ``GenerateProvenanceUseCase``.

These tests document the intended behaviour and the dependency-injection
pattern used to make the use case unit-testable -- every dependency is a
fake implementing the same ``Protocol`` as the real adapter.
"""

from __future__ import annotations

from pathlib import Path

from hpc_provenance.application.dto.requests import GenerateProvenanceRequest
from hpc_provenance.application.use_cases.generate_provenance import GenerateProvenanceUseCase
from hpc_provenance.domain.models.artifact import Artifact
from hpc_provenance.domain.models.git_metadata import GitRepositoryMetadata
from hpc_provenance.domain.models.in_toto import InTotoStatement
from hpc_provenance.domain.models.provenance import (
    BuildDefinition,
    BuilderIdentity,
    BuildMetadata,
    RunDetails,
    SLSAProvenancePredicate,
)
from hpc_provenance.domain.models.scheduler_metadata import SlurmJobMetadata
from hpc_provenance.infrastructure.provenance.in_toto_statement_builder import (
    InTotoV1StatementBuilder,
)
from hpc_provenance.infrastructure.provenance.slsa_predicate_builder import (
    SLSA_V1_PREDICATE_TYPE,
    SLSAv1PredicateBuilder,
)
from hpc_provenance.infrastructure.provenance.slsa_predicate_mapper import (
    resource_descriptor_from_artifact,
)
from tests.fakes.clock import FixedClock
from tests.fakes.collectors import (
    FakeArtifactMetadataCollector,
    FakeGitMetadataCollector,
    FakeSchedulerMetadataCollector,
)
from tests.fakes.provenance import FakeInTotoStatementBuilder, FakeProvenancePredicateBuilder


def test_execute_returns_statement_from_builder(
    fixed_clock: FixedClock,
    sample_git_metadata: GitRepositoryMetadata,
    sample_job_metadata: SlurmJobMetadata,
    sample_product_artifact: Artifact,
) -> None:
    predicate = SLSAProvenancePredicate(
        build_definition=BuildDefinition(
            build_type="https://example.org/hpc-provenance/build-types/slurm-job/v1",
            external_parameters={},
            internal_parameters={},
        ),
        run_details=RunDetails(
            builder=BuilderIdentity(id="https://example.org/hpc-provenance/builder/v1"),
            metadata=BuildMetadata(invocation_id="123456", started_on=None, finished_on=None),
        ),
    )
    expected_statement = InTotoStatement(
        subjects=(), predicate_type="https://slsa.dev/provenance/v1", predicate={}
    )

    use_case = GenerateProvenanceUseCase(
        git_collector=FakeGitMetadataCollector(result=sample_git_metadata),
        scheduler_collector=FakeSchedulerMetadataCollector(result=sample_job_metadata),
        artifact_collector=FakeArtifactMetadataCollector(result=(sample_product_artifact,)),
        predicate_builder=FakeProvenancePredicateBuilder(result=predicate),
        statement_builder=FakeInTotoStatementBuilder(result=expected_statement),
        clock=fixed_clock,
    )

    request = GenerateProvenanceRequest(
        builder_id="https://example.org/hpc-provenance/builder/v1",
        product_paths=(Path("/work/project/out/model.safetensors"),),
        git_repository_path=Path("/work/project"),
    )

    statement = use_case.execute(request)

    assert statement == expected_statement


def test_execute_with_real_builders_maps_collected_metadata(
    fixed_clock: FixedClock,
    sample_git_metadata: GitRepositoryMetadata,
    sample_job_metadata: SlurmJobMetadata,
    sample_product_artifact: Artifact,
) -> None:
    use_case = GenerateProvenanceUseCase(
        git_collector=FakeGitMetadataCollector(result=sample_git_metadata),
        scheduler_collector=FakeSchedulerMetadataCollector(result=sample_job_metadata),
        artifact_collector=FakeArtifactMetadataCollector(result=(sample_product_artifact,)),
        predicate_builder=SLSAv1PredicateBuilder(),
        statement_builder=InTotoV1StatementBuilder(),
        clock=fixed_clock,
    )

    request = GenerateProvenanceRequest(
        builder_id="https://example.org/hpc-provenance/builder/v1",
        product_paths=(Path("/work/project/out/model.safetensors"),),
        git_repository_path=Path("/work/project"),
    )

    statement = use_case.execute(request)

    assert statement.predicate_type == SLSA_V1_PREDICATE_TYPE
    assert statement.subjects == (resource_descriptor_from_artifact(sample_product_artifact),)

    build_definition = statement.predicate["buildDefinition"]
    assert build_definition["buildType"] == "https://hpc-provenance.dev/build-types/slurm-job/v1"
    assert build_definition["internalParameters"]["jobId"] == str(sample_job_metadata.job_id)

    run_details = statement.predicate["runDetails"]
    assert run_details["builder"]["id"] == "https://example.org/hpc-provenance/builder/v1"
    assert run_details["metadata"]["invocationId"] == str(sample_job_metadata.job_id)
