"""Unit tests for provenance-generation domain models -- pure data, no doubles needed."""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from hpc_provenance.domain.enums import DigestAlgorithm
from hpc_provenance.domain.exceptions import InvalidMetadataError
from hpc_provenance.domain.models.provenance import BuilderIdentity, RunDetails
from hpc_provenance.domain.models.provenance_metadata import (
    ArtifactMetadata,
    BuilderMetadata,
    BuildMetadata,
    InvocationMetadata,
    Subject,
)
from hpc_provenance.domain.value_objects import Digest


def _digest(
    hex_value: str = "a" * 64, algorithm: DigestAlgorithm = DigestAlgorithm.SHA256
) -> Digest:
    return Digest(algorithm=algorithm, hex_value=hex_value)


# --- Subject ---------------------------------------------------------------


def test_subject_to_dict() -> None:
    subject = Subject(name="model.safetensors", digests=(_digest(),))

    assert subject.to_dict() == {"name": "model.safetensors", "digest": {"sha256": "a" * 64}}


def test_subject_to_json_round_trips() -> None:
    subject = Subject(name="model.safetensors", digests=(_digest(),))

    assert json.loads(subject.to_json()) == subject.to_dict()


def test_subject_merges_multiple_digest_algorithms() -> None:
    subject = Subject(
        name="model.safetensors",
        digests=(_digest(), _digest(hex_value="b" * 40, algorithm=DigestAlgorithm.SHA1)),
    )

    assert subject.to_dict()["digest"] == {"sha256": "a" * 64, "sha1": "b" * 40}


def test_subject_is_immutable() -> None:
    subject = Subject(name="model.safetensors", digests=(_digest(),))

    with pytest.raises(dataclasses.FrozenInstanceError):
        subject.name = "other"  # type: ignore[misc]


def test_subject_rejects_empty_name() -> None:
    with pytest.raises(InvalidMetadataError):
        Subject(name="", digests=(_digest(),))


def test_subject_rejects_no_digests() -> None:
    with pytest.raises(InvalidMetadataError):
        Subject(name="model.safetensors", digests=())


def test_subject_rejects_duplicate_digest_algorithm() -> None:
    with pytest.raises(InvalidMetadataError):
        Subject(name="model.safetensors", digests=(_digest(), _digest(hex_value="c" * 64)))


# --- ArtifactMetadata --------------------------------------------------------


def test_artifact_metadata_to_dict() -> None:
    local_path = Path("/work/out/model.safetensors")
    artifact = ArtifactMetadata(
        name="model.safetensors",
        digests=(_digest(),),
        uri="file:///work/out/model.safetensors",
        media_type="application/octet-stream",
        size_bytes=123,
        local_path=local_path,
    )

    assert artifact.to_dict() == {
        "name": "model.safetensors",
        "digest": {"sha256": "a" * 64},
        "uri": "file:///work/out/model.safetensors",
        "mediaType": "application/octet-stream",
        "sizeBytes": 123,
        "localPath": str(local_path),
    }


def test_artifact_metadata_defaults_to_dict() -> None:
    artifact = ArtifactMetadata(name="model.safetensors", digests=(_digest(),))

    assert artifact.to_dict() == {
        "name": "model.safetensors",
        "digest": {"sha256": "a" * 64},
        "uri": None,
        "mediaType": None,
        "sizeBytes": None,
        "localPath": None,
    }


def test_artifact_metadata_to_json_round_trips() -> None:
    artifact = ArtifactMetadata(name="model.safetensors", digests=(_digest(),), size_bytes=123)

    assert json.loads(artifact.to_json()) == artifact.to_dict()


def test_artifact_metadata_as_subject() -> None:
    artifact = ArtifactMetadata(name="model.safetensors", digests=(_digest(),))

    assert artifact.as_subject() == Subject(name="model.safetensors", digests=(_digest(),))


def test_artifact_metadata_rejects_empty_name() -> None:
    with pytest.raises(InvalidMetadataError):
        ArtifactMetadata(name="", digests=(_digest(),))


def test_artifact_metadata_rejects_no_digests() -> None:
    with pytest.raises(InvalidMetadataError):
        ArtifactMetadata(name="model.safetensors", digests=())


def test_artifact_metadata_rejects_negative_size() -> None:
    with pytest.raises(InvalidMetadataError):
        ArtifactMetadata(name="model.safetensors", digests=(_digest(),), size_bytes=-1)


def test_artifact_metadata_rejects_blank_uri() -> None:
    with pytest.raises(InvalidMetadataError):
        ArtifactMetadata(name="model.safetensors", digests=(_digest(),), uri="   ")


# --- BuilderMetadata ----------------------------------------------------------


def test_builder_metadata_to_dict() -> None:
    builder = BuilderMetadata(
        id="https://example.org/hpc-provenance/builder/v1",
        name="slurm-cluster-01",
        version="23.02.1",
    )

    assert builder.to_dict() == {
        "id": "https://example.org/hpc-provenance/builder/v1",
        "name": "slurm-cluster-01",
        "version": "23.02.1",
    }


def test_builder_metadata_defaults_to_dict() -> None:
    builder = BuilderMetadata(id="https://example.org/hpc-provenance/builder/v1")

    assert builder.to_dict() == {
        "id": "https://example.org/hpc-provenance/builder/v1",
        "name": None,
        "version": None,
    }


def test_builder_metadata_to_json_round_trips() -> None:
    builder = BuilderMetadata(id="https://example.org/hpc-provenance/builder/v1")

    assert json.loads(builder.to_json()) == builder.to_dict()


def test_builder_metadata_rejects_empty_id() -> None:
    with pytest.raises(InvalidMetadataError):
        BuilderMetadata(id="")


def test_builder_metadata_rejects_blank_name() -> None:
    with pytest.raises(InvalidMetadataError):
        BuilderMetadata(id="https://example.org/builder", name="   ")


def test_builder_metadata_rejects_blank_version() -> None:
    with pytest.raises(InvalidMetadataError):
        BuilderMetadata(id="https://example.org/builder", version="")


# --- InvocationMetadata --------------------------------------------------------


def test_invocation_metadata_to_dict() -> None:
    started = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    finished = datetime(2026, 1, 1, 1, 0, tzinfo=UTC)
    invocation = InvocationMetadata(
        invocation_id="123456",
        command=("python", "train.py", "--epochs", "10"),
        working_directory=Path("/work/project"),
        environment={"CUDA_VISIBLE_DEVICES": "0"},
        parameters={"epochs": 10},
        started_at=started,
        finished_at=finished,
    )

    assert invocation.to_dict() == {
        "invocationId": "123456",
        "command": ["python", "train.py", "--epochs", "10"],
        "workingDirectory": str(Path("/work/project")),
        "environment": {"CUDA_VISIBLE_DEVICES": "0"},
        "parameters": {"epochs": 10},
        "startedAt": started.isoformat(),
        "finishedAt": finished.isoformat(),
    }


def test_invocation_metadata_defaults_to_dict() -> None:
    invocation = InvocationMetadata(
        invocation_id="123456",
        command=("python", "train.py"),
        working_directory=Path("/work/project"),
    )

    assert invocation.to_dict() == {
        "invocationId": "123456",
        "command": ["python", "train.py"],
        "workingDirectory": str(Path("/work/project")),
        "environment": {},
        "parameters": {},
        "startedAt": None,
        "finishedAt": None,
    }


def test_invocation_metadata_to_json_round_trips() -> None:
    invocation = InvocationMetadata(
        invocation_id="123456", command=("python",), working_directory=Path(".")
    )

    assert json.loads(invocation.to_json()) == invocation.to_dict()


def test_invocation_metadata_rejects_empty_invocation_id() -> None:
    with pytest.raises(InvalidMetadataError):
        InvocationMetadata(invocation_id="", command=("python",), working_directory=Path("."))


def test_invocation_metadata_rejects_empty_command() -> None:
    with pytest.raises(InvalidMetadataError):
        InvocationMetadata(invocation_id="123456", command=(), working_directory=Path("."))


def test_invocation_metadata_rejects_finished_before_started() -> None:
    started = datetime(2026, 1, 1, 1, 0, tzinfo=UTC)
    finished = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)

    with pytest.raises(InvalidMetadataError):
        InvocationMetadata(
            invocation_id="123456",
            command=("python",),
            working_directory=Path("."),
            started_at=started,
            finished_at=finished,
        )


# --- BuildMetadata --------------------------------------------------------------


def test_build_metadata_to_dict() -> None:
    started = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    finished = datetime(2026, 1, 1, 1, 0, tzinfo=UTC)
    metadata = BuildMetadata(invocation_id="123456", started_on=started, finished_on=finished)

    assert metadata.to_dict() == {
        "invocationId": "123456",
        "startedOn": started.isoformat(),
        "finishedOn": finished.isoformat(),
    }


def test_build_metadata_allows_all_none_fields() -> None:
    metadata = BuildMetadata(invocation_id=None, started_on=None, finished_on=None)

    assert metadata.to_dict() == {"invocationId": None, "startedOn": None, "finishedOn": None}


def test_build_metadata_to_json_round_trips() -> None:
    metadata = BuildMetadata(invocation_id="123456", started_on=None, finished_on=None)

    assert json.loads(metadata.to_json()) == metadata.to_dict()


def test_build_metadata_rejects_blank_invocation_id() -> None:
    with pytest.raises(InvalidMetadataError):
        BuildMetadata(invocation_id="   ", started_on=None, finished_on=None)


def test_build_metadata_rejects_finished_before_started() -> None:
    started = datetime(2026, 1, 1, 1, 0, tzinfo=UTC)
    finished = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)

    with pytest.raises(InvalidMetadataError):
        BuildMetadata(invocation_id="123456", started_on=started, finished_on=finished)


def test_build_metadata_is_used_as_run_details_metadata() -> None:
    run_details = RunDetails(
        builder=BuilderIdentity(id="https://example.org/hpc-provenance/builder/v1"),
        metadata=BuildMetadata(invocation_id="123456", started_on=None, finished_on=None),
    )

    assert run_details.metadata.invocation_id == "123456"
