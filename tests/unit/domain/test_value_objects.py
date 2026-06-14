"""Unit tests for domain value objects -- pure data, no doubles needed."""

from __future__ import annotations

from hpc_provenance.domain.enums import DigestAlgorithm, SchedulerType
from hpc_provenance.domain.value_objects import Digest, JobIdentifier


def test_digest_as_digest_set() -> None:
    digest = Digest(algorithm=DigestAlgorithm.SHA256, hex_value="deadbeef")

    assert digest.as_digest_set() == {"sha256": "deadbeef"}


def test_digest_str() -> None:
    digest = Digest(algorithm=DigestAlgorithm.SHA256, hex_value="deadbeef")

    assert str(digest) == "sha256:deadbeef"


def test_job_identifier_str_without_array_index() -> None:
    job_id = JobIdentifier(scheduler=SchedulerType.SLURM, value="123456")

    assert str(job_id) == "slurm:123456"


def test_job_identifier_str_with_array_index() -> None:
    job_id = JobIdentifier(scheduler=SchedulerType.SLURM, value="123456", array_index="7")

    assert str(job_id) == "slurm:123456_7"
