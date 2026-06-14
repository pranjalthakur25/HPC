"""Unit tests for ``infrastructure.provenance.slsa_predicate_mapper``."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from pathlib import Path

import pytest

from hpc_provenance.domain.exceptions import ProvenanceGenerationError
from hpc_provenance.domain.models.artifact import Artifact
from hpc_provenance.domain.models.git_metadata import GitRepositoryMetadata
from hpc_provenance.domain.models.provenance import (
    BuildDefinition,
    BuilderIdentity,
    ResourceDescriptor,
    RunDetails,
)
from hpc_provenance.domain.models.provenance_context import ProvenanceContext
from hpc_provenance.domain.models.provenance_metadata import BuildMetadata
from hpc_provenance.infrastructure.provenance.slsa_predicate_mapper import (
    build_definition_from_context,
    build_definition_to_dict,
    builder_identity_to_dict,
    resource_descriptor_from_artifact,
    resource_descriptor_from_git_metadata,
    resource_descriptor_to_dict,
    run_details_from_context,
    run_details_to_dict,
)

# --- resource_descriptor_from_artifact --------------------------------------


def test_resource_descriptor_from_artifact_includes_size_annotation(
    sample_product_artifact: Artifact,
) -> None:
    descriptor = resource_descriptor_from_artifact(sample_product_artifact)

    assert descriptor.name == "model.safetensors"
    assert descriptor.uri == "file:///work/project/out/model.safetensors"
    assert descriptor.digest == {"sha256": "b" * 64}
    assert descriptor.media_type == "application/octet-stream"
    assert descriptor.annotations == {"sizeBytes": 123456}


def test_resource_descriptor_from_artifact_omits_size_when_unknown(
    sample_product_artifact: Artifact,
) -> None:
    artifact = dataclasses.replace(sample_product_artifact, size_bytes=None)

    descriptor = resource_descriptor_from_artifact(artifact)

    assert descriptor.annotations is None


# --- resource_descriptor_from_git_metadata ----------------------------------


def test_resource_descriptor_from_git_metadata(sample_git_metadata: GitRepositoryMetadata) -> None:
    descriptor = resource_descriptor_from_git_metadata(sample_git_metadata)

    assert descriptor.uri == "https://github.com/example/project.git"
    assert descriptor.digest == {"gitCommit": "a" * 40}
    assert descriptor.annotations == {"isDirty": False, "branch": "main"}


def test_resource_descriptor_from_git_metadata_includes_tags(
    sample_git_metadata: GitRepositoryMetadata,
) -> None:
    dirty_tagged = dataclasses.replace(sample_git_metadata, is_dirty=True, tags=("v1.0.0",))

    descriptor = resource_descriptor_from_git_metadata(dirty_tagged)

    assert descriptor.annotations == {"isDirty": True, "branch": "main", "tags": ["v1.0.0"]}


# --- build_definition_from_context -------------------------------------------


def test_build_definition_from_context(sample_provenance_context: ProvenanceContext) -> None:
    build_definition = build_definition_from_context(sample_provenance_context)

    assert build_definition.build_type == "https://hpc-provenance.dev/build-types/slurm-job/v1"
    assert build_definition.external_parameters == {
        "jobScript": "sbatch train.slurm",
        "workingDirectory": str(Path("/work/project")),
    }
    assert build_definition.internal_parameters == {
        "scheduler": "slurm",
        "jobId": "slurm:123456",
        "jobName": "train-model",
        "user": "jdoe",
        "account": "research",
        "state": "completed",
        "exitCode": 0,
        "partition": "gpu",
        "numNodes": 2,
        "numTasks": 2,
        "cpusPerTask": 8,
        "gpusPerNode": 4,
        "nodeList": ["node001", "node002"],
    }
    # one entry for the material artifact, one for the git repository
    assert len(build_definition.resolved_dependencies) == 2
    assert build_definition.resolved_dependencies[0].name == "train.py"
    assert build_definition.resolved_dependencies[1].digest == {"gitCommit": "a" * 40}


def test_build_definition_from_context_without_git_metadata(
    sample_provenance_context: ProvenanceContext,
) -> None:
    context = dataclasses.replace(sample_provenance_context, git_metadata=None)

    build_definition = build_definition_from_context(context)

    assert len(build_definition.resolved_dependencies) == 1
    assert build_definition.resolved_dependencies[0].name == "train.py"


def test_build_definition_from_context_rejects_unsupported_scheduler(
    sample_provenance_context: ProvenanceContext,
) -> None:
    job_metadata = sample_provenance_context.job_metadata
    unsupported_job_id = dataclasses.replace(job_metadata.job_id, scheduler="pbs")
    context = dataclasses.replace(
        sample_provenance_context,
        job_metadata=dataclasses.replace(job_metadata, job_id=unsupported_job_id),
    )

    with pytest.raises(ProvenanceGenerationError):
        build_definition_from_context(context)


# --- run_details_from_context -------------------------------------------------


def test_run_details_from_context(sample_provenance_context: ProvenanceContext) -> None:
    run_details = run_details_from_context(sample_provenance_context)

    assert run_details.builder == BuilderIdentity(
        id="https://example.org/hpc-provenance/builder/v1"
    )
    assert run_details.metadata == BuildMetadata(
        invocation_id="slurm:123456",
        started_on=datetime(2025, 12, 31, 23, 5, tzinfo=UTC),
        finished_on=datetime(2026, 1, 1, 1, 0, tzinfo=UTC),
    )
    assert run_details.byproducts == ()


# --- resource_descriptor_to_dict ----------------------------------------------


def test_resource_descriptor_to_dict_omits_unset_fields() -> None:
    assert resource_descriptor_to_dict(ResourceDescriptor()) == {}


def test_resource_descriptor_to_dict_includes_set_fields() -> None:
    descriptor = ResourceDescriptor(
        name="model.safetensors",
        uri="file:///out/model.safetensors",
        digest={"sha256": "b" * 64},
        download_location="https://example.org/artifacts/model.safetensors",
        media_type="application/octet-stream",
        annotations={"sizeBytes": 123456},
    )

    assert resource_descriptor_to_dict(descriptor) == {
        "name": "model.safetensors",
        "uri": "file:///out/model.safetensors",
        "digest": {"sha256": "b" * 64},
        "downloadLocation": "https://example.org/artifacts/model.safetensors",
        "mediaType": "application/octet-stream",
        "annotations": {"sizeBytes": 123456},
    }


# --- builder_identity_to_dict --------------------------------------------------


def test_builder_identity_to_dict_minimal() -> None:
    builder = BuilderIdentity(id="https://example.org/hpc-provenance/builder/v1")

    assert builder_identity_to_dict(builder) == {"id": "https://example.org/hpc-provenance/builder/v1"}


def test_builder_identity_to_dict_with_version_and_dependencies() -> None:
    dependency = ResourceDescriptor(uri="https://example.org/tools/slurm", digest={"sha256": "d" * 64})
    builder = BuilderIdentity(
        id="https://example.org/hpc-provenance/builder/v1",
        version={"slurm": "23.02.1"},
        builder_dependencies=(dependency,),
    )

    assert builder_identity_to_dict(builder) == {
        "id": "https://example.org/hpc-provenance/builder/v1",
        "version": {"slurm": "23.02.1"},
        "builderDependencies": [resource_descriptor_to_dict(dependency)],
    }


# --- build_definition_to_dict --------------------------------------------------


def test_build_definition_to_dict_without_resolved_dependencies() -> None:
    build_definition = BuildDefinition(
        build_type="https://hpc-provenance.dev/build-types/slurm-job/v1",
        external_parameters={"jobScript": "sbatch train.slurm"},
        internal_parameters={"scheduler": "slurm"},
    )

    result = build_definition_to_dict(build_definition)

    assert result == {
        "buildType": "https://hpc-provenance.dev/build-types/slurm-job/v1",
        "externalParameters": {"jobScript": "sbatch train.slurm"},
        "internalParameters": {"scheduler": "slurm"},
    }
    assert "resolvedDependencies" not in result


def test_build_definition_to_dict_with_resolved_dependencies() -> None:
    dependency = ResourceDescriptor(uri="https://github.com/example/project.git")
    build_definition = BuildDefinition(
        build_type="https://hpc-provenance.dev/build-types/slurm-job/v1",
        external_parameters={},
        internal_parameters={},
        resolved_dependencies=(dependency,),
    )

    result = build_definition_to_dict(build_definition)

    assert result["resolvedDependencies"] == [resource_descriptor_to_dict(dependency)]


# --- run_details_to_dict --------------------------------------------------------


def test_run_details_to_dict_without_byproducts() -> None:
    run_details = RunDetails(
        builder=BuilderIdentity(id="https://example.org/hpc-provenance/builder/v1"),
        metadata=BuildMetadata(invocation_id="123456", started_on=None, finished_on=None),
    )

    result = run_details_to_dict(run_details)

    assert result == {
        "builder": {"id": "https://example.org/hpc-provenance/builder/v1"},
        "metadata": run_details.metadata.to_dict(),
    }
    assert "byproducts" not in result


def test_run_details_to_dict_with_byproducts() -> None:
    byproduct = ResourceDescriptor(name="job.log", uri="file:///work/project/job.log")
    run_details = RunDetails(
        builder=BuilderIdentity(id="https://example.org/hpc-provenance/builder/v1"),
        metadata=BuildMetadata(invocation_id="123456", started_on=None, finished_on=None),
        byproducts=(byproduct,),
    )

    result = run_details_to_dict(run_details)

    assert result["byproducts"] == [resource_descriptor_to_dict(byproduct)]
