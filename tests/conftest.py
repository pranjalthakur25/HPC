"""Shared pytest fixtures: sample domain objects and fake adapters."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from hpc_provenance.domain.enums import ArtifactRole, DigestAlgorithm, JobState, SchedulerType
from hpc_provenance.domain.models.artifact import Artifact
from hpc_provenance.domain.models.git_metadata import GitCommit, GitRepositoryMetadata
from hpc_provenance.domain.models.provenance_context import ProvenanceContext
from hpc_provenance.domain.models.scheduler_metadata import (
    JobExecutionWindow,
    ResourceAllocation,
    SlurmJobMetadata,
)
from hpc_provenance.domain.value_objects import Digest, JobIdentifier, SigningKey, VerificationKey
from tests.fakes.clock import FixedClock


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def fixed_clock(fixed_now: datetime) -> FixedClock:
    return FixedClock(fixed_time=fixed_now)


@pytest.fixture
def sample_git_metadata() -> GitRepositoryMetadata:
    return GitRepositoryMetadata(
        remote_url="https://github.com/example/project.git",
        branch="main",
        tags=(),
        is_dirty=False,
        root_path=Path("/work/project"),
        commit=GitCommit(
            sha="a" * 40,
            author_name="Jane Doe",
            author_email="jane@example.org",
            committed_at=datetime(2025, 12, 31, tzinfo=UTC),
            message="Add training script",
        ),
    )


@pytest.fixture
def sample_job_metadata() -> SlurmJobMetadata:
    return SlurmJobMetadata(
        job_id=JobIdentifier(scheduler=SchedulerType.SLURM, value="123456"),
        job_name="train-model",
        user_name="jdoe",
        account="research",
        state=JobState.COMPLETED,
        exit_code=0,
        working_directory=Path("/work/project"),
        submit_command=("sbatch", "train.slurm"),
        environment={},
        allocation=ResourceAllocation(
            num_nodes=2,
            num_tasks=2,
            cpus_per_task=8,
            node_list=("node001", "node002"),
            partition="gpu",
            gpus_per_node=4,
        ),
        execution_window=JobExecutionWindow(
            submitted_at=datetime(2025, 12, 31, 23, 0, tzinfo=UTC),
            started_at=datetime(2025, 12, 31, 23, 5, tzinfo=UTC),
            finished_at=datetime(2026, 1, 1, 1, 0, tzinfo=UTC),
        ),
    )


@pytest.fixture
def sample_product_artifact() -> Artifact:
    return Artifact(
        name="model.safetensors",
        uri="file:///work/project/out/model.safetensors",
        digest=Digest(algorithm=DigestAlgorithm.SHA256, hex_value="b" * 64),
        media_type="application/octet-stream",
        size_bytes=123456,
        role=ArtifactRole.PRODUCT,
    )


@pytest.fixture
def sample_material_artifact() -> Artifact:
    return Artifact(
        name="train.py",
        uri="file:///work/project/train.py",
        digest=Digest(algorithm=DigestAlgorithm.SHA256, hex_value="c" * 64),
        media_type="text/x-python",
        size_bytes=2048,
        role=ArtifactRole.MATERIAL,
    )


@pytest.fixture
def sample_provenance_context(
    sample_git_metadata: GitRepositoryMetadata,
    sample_job_metadata: SlurmJobMetadata,
    sample_material_artifact: Artifact,
    sample_product_artifact: Artifact,
) -> ProvenanceContext:
    window = sample_job_metadata.execution_window
    return ProvenanceContext(
        job_metadata=sample_job_metadata,
        materials=(sample_material_artifact,),
        products=(sample_product_artifact,),
        builder_id="https://example.org/hpc-provenance/builder/v1",
        invocation_id=str(sample_job_metadata.job_id),
        started_at=window.started_at,
        git_metadata=sample_git_metadata,
        finished_at=window.finished_at,
    )


def _pem_key_pair(private_key: RSAPrivateKey | EllipticCurvePrivateKey) -> tuple[bytes, bytes]:
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


@pytest.fixture(scope="session")
def rsa_key_pair() -> tuple[SigningKey, VerificationKey]:
    private_pem, public_pem = _pem_key_pair(
        rsa.generate_private_key(public_exponent=65537, key_size=2048)
    )
    return (
        SigningKey(key_id="rsa-key-1", algorithm="rsa", private_key_material=private_pem),
        VerificationKey(key_id="rsa-key-1", algorithm="rsa", public_key_material=public_pem),
    )


@pytest.fixture(scope="session")
def ec_key_pair() -> tuple[SigningKey, VerificationKey]:
    private_pem, public_pem = _pem_key_pair(ec.generate_private_key(ec.SECP256R1()))
    return (
        SigningKey(key_id="ec-key-1", algorithm="ecdsa", private_key_material=private_pem),
        VerificationKey(key_id="ec-key-1", algorithm="ecdsa", public_key_material=public_pem),
    )
