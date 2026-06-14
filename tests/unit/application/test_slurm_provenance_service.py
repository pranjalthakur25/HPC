"""Unit tests for ``SlurmProvenanceService``."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from hpc_provenance.application.services.slurm_provenance_service import SlurmProvenanceService
from hpc_provenance.application.use_cases.generate_provenance import GenerateProvenanceUseCase
from hpc_provenance.application.use_cases.sign_provenance import SignProvenanceUseCase
from hpc_provenance.domain.models.artifact import Artifact
from hpc_provenance.domain.models.git_metadata import GitRepositoryMetadata
from hpc_provenance.domain.models.scheduler_metadata import SlurmJobMetadata
from hpc_provenance.domain.value_objects import SigningKey, VerificationKey
from hpc_provenance.infrastructure.provenance.in_toto_statement_builder import InTotoV1StatementBuilder
from hpc_provenance.infrastructure.provenance.slsa_predicate_builder import SLSAv1PredicateBuilder
from hpc_provenance.infrastructure.signing.dsse_signer import DsseSigner
from hpc_provenance.infrastructure.signing.payload_signers import create_payload_signer
from tests.fakes.clock import FixedClock
from tests.fakes.collectors import (
    FakeArtifactMetadataCollector,
    FakeGitMetadataCollector,
    FakeSchedulerMetadataCollector,
)
from tests.fakes.repositories import InMemoryKeyRepository, InMemoryProvenanceRepository

BUILDER_ID = "https://example.org/hpc-provenance/builder/v1"


@pytest.fixture
def job_metadata(sample_job_metadata: SlurmJobMetadata, tmp_path: Path) -> SlurmJobMetadata:
    return replace(sample_job_metadata, working_directory=tmp_path)


@pytest.fixture
def service(
    job_metadata: SlurmJobMetadata,
    sample_git_metadata: GitRepositoryMetadata,
    sample_product_artifact: Artifact,
    fixed_clock: FixedClock,
    rsa_key_pair: tuple[SigningKey, VerificationKey],
) -> SlurmProvenanceService:
    signing_key, _ = rsa_key_pair

    generate_use_case = GenerateProvenanceUseCase(
        git_collector=FakeGitMetadataCollector(result=sample_git_metadata),
        scheduler_collector=FakeSchedulerMetadataCollector(result=job_metadata),
        artifact_collector=FakeArtifactMetadataCollector(result=(sample_product_artifact,)),
        predicate_builder=SLSAv1PredicateBuilder(),
        statement_builder=InTotoV1StatementBuilder(),
        clock=fixed_clock,
    )
    sign_use_case = SignProvenanceUseCase(
        envelope_signer=DsseSigner(),
        key_repository=InMemoryKeyRepository(signing_keys={signing_key.key_id: signing_key}),
        provenance_repository=InMemoryProvenanceRepository(),
        payload_signer_factory=create_payload_signer,
    )

    return SlurmProvenanceService(
        scheduler_collector=FakeSchedulerMetadataCollector(result=job_metadata),
        git_collector=FakeGitMetadataCollector(result=sample_git_metadata),
        generate_use_case=generate_use_case,
        sign_use_case=sign_use_case,
    )


def test_run_prologue_writes_snapshot_with_git_metadata(
    service: SlurmProvenanceService,
    job_metadata: SlurmJobMetadata,
    sample_git_metadata: GitRepositoryMetadata,
    tmp_path: Path,
) -> None:
    path = service.run_prologue(git_repository_path=tmp_path, output_dir=tmp_path)

    assert path == tmp_path / "prologue.json"
    snapshot = json.loads(path.read_text())
    assert snapshot["jobId"] == str(job_metadata.job_id)
    assert snapshot["jobName"] == job_metadata.job_name
    assert snapshot["user"] == job_metadata.user_name
    assert snapshot["partition"] == job_metadata.allocation.partition
    assert snapshot["nodeList"] == list(job_metadata.allocation.node_list)
    assert snapshot["submitDir"] == str(job_metadata.working_directory)
    assert snapshot["git"]["remoteUrl"] == sample_git_metadata.remote_url
    assert snapshot["git"]["branch"] == sample_git_metadata.branch
    assert snapshot["git"]["commit"] == sample_git_metadata.commit.sha
    assert snapshot["git"]["isDirty"] == sample_git_metadata.is_dirty


def test_run_prologue_without_git_repo_omits_git_section(
    service: SlurmProvenanceService, tmp_path: Path
) -> None:
    path = service.run_prologue(output_dir=tmp_path)

    snapshot = json.loads(path.read_text())
    assert "git" not in snapshot


def test_run_epilogue_writes_provenance_and_attestation(
    service: SlurmProvenanceService,
    job_metadata: SlurmJobMetadata,
    rsa_key_pair: tuple[SigningKey, VerificationKey],
    tmp_path: Path,
) -> None:
    signing_key, _ = rsa_key_pair
    product = tmp_path / "model.safetensors"
    product.write_bytes(b"model weights")

    result = service.run_epilogue(
        builder_id=BUILDER_ID,
        signing_key_ids=(signing_key.key_id,),
        product_paths=(product,),
        output_dir=tmp_path,
    )

    assert result.statement_path == tmp_path / "provenance.json"
    assert result.envelope_path == tmp_path / "attestation.dsse"

    statement = json.loads(result.statement_path.read_text())
    assert statement["predicateType"] == "https://slsa.dev/provenance/v1"
    assert (
        statement["predicate"]["buildDefinition"]["internalParameters"]["jobId"]
        == str(job_metadata.job_id)
    )

    envelope = json.loads(result.envelope_path.read_text())
    assert envelope["payloadType"] == "application/vnd.in-toto+json"
    assert envelope["signatures"][0]["keyid"] == signing_key.key_id

    saved = service.sign_use_case.provenance_repository.get(result.record_id)
    assert saved.payload_type == "application/vnd.in-toto+json"
