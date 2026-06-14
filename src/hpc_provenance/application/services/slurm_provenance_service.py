"""Slurm prologue/epilogue orchestration for provenance generation.

Both ``run_prologue`` and ``run_epilogue`` are designed to be invoked from a
user's own ``sbatch`` script (no scheduler-admin privileges required); see
``examples/train.sh``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from hpc_provenance.application.dto.requests import GenerateProvenanceRequest, SignProvenanceRequest
from hpc_provenance.application.dto.results import SlurmProvenanceResult
from hpc_provenance.application.use_cases.generate_provenance import GenerateProvenanceUseCase
from hpc_provenance.application.use_cases.sign_provenance import SignProvenanceUseCase
from hpc_provenance.domain.interfaces.collectors import GitMetadataCollector, SchedulerMetadataCollector


@dataclass(frozen=True, slots=True)
class SlurmProvenanceService:
    """Generates and signs provenance for a Slurm job, using
    environment-variable-based metadata collection (``SlurmEnvMetadataCollector``).

    See ``ARCHITECTURE.md`` section 7.4 for the prologue/epilogue sequence.
    """

    scheduler_collector: SchedulerMetadataCollector
    git_collector: GitMetadataCollector
    generate_use_case: GenerateProvenanceUseCase
    sign_use_case: SignProvenanceUseCase

    def run_prologue(
        self,
        *,
        git_repository_path: Path | None = None,
        output_dir: Path | None = None,
    ) -> Path:
        """Write a job-start snapshot to ``<output_dir>/prologue.json``.

        Informational only: ``run_epilogue`` re-collects all metadata
        independently and does not depend on this file.

        Returns:
            The path of the written ``prologue.json``.
        """
        job_metadata = self.scheduler_collector.collect()
        git_metadata = (
            self.git_collector.collect(git_repository_path)
            if git_repository_path is not None
            else None
        )

        target_dir = output_dir or job_metadata.working_directory
        target_dir.mkdir(parents=True, exist_ok=True)

        snapshot: dict[str, object] = {
            "jobId": str(job_metadata.job_id),
            "jobName": job_metadata.job_name,
            "user": job_metadata.user_name,
            "partition": job_metadata.allocation.partition,
            "nodeList": list(job_metadata.allocation.node_list),
            "submitDir": str(job_metadata.working_directory),
        }
        if git_metadata is not None:
            snapshot["git"] = {
                "remoteUrl": git_metadata.remote_url,
                "branch": git_metadata.branch,
                "commit": git_metadata.commit.sha,
                "isDirty": git_metadata.is_dirty,
            }

        prologue_path = target_dir / "prologue.json"
        prologue_path.write_text(json.dumps(snapshot, indent=2))
        return prologue_path

    def run_epilogue(
        self,
        *,
        builder_id: str,
        signing_key_ids: tuple[str, ...],
        product_paths: tuple[Path, ...],
        material_paths: tuple[Path, ...] = (),
        git_repository_path: Path | None = None,
        output_dir: Path | None = None,
    ) -> SlurmProvenanceResult:
        """Generate and sign provenance for the just-completed job, writing
        ``provenance.json`` and ``attestation.dsse`` to ``<output_dir>``.

        Returns:
            A ``SlurmProvenanceResult`` with the paths written and the
            ``ProvenanceRecordId`` assigned by ``provenance_repository``.
        """
        job_metadata = self.scheduler_collector.collect()

        generate_request = GenerateProvenanceRequest(
            builder_id=builder_id,
            product_paths=product_paths,
            material_paths=material_paths,
            job_id=job_metadata.job_id,
            git_repository_path=git_repository_path,
        )
        statement = self.generate_use_case.execute(generate_request)

        target_dir = output_dir or job_metadata.working_directory
        target_dir.mkdir(parents=True, exist_ok=True)

        statement_path = target_dir / "provenance.json"
        statement_path.write_text(statement.to_json())

        sign_request = SignProvenanceRequest(
            statement=statement,
            signing_key_ids=signing_key_ids,
            metadata={"job_id": str(job_metadata.job_id), "user": job_metadata.user_name},
        )
        sign_result = self.sign_use_case.execute(sign_request)

        envelope_path = target_dir / "attestation.dsse"
        envelope_path.write_text(sign_result.envelope.to_json())

        return SlurmProvenanceResult(
            statement_path=statement_path,
            envelope_path=envelope_path,
            record_id=sign_result.record_id,
        )
