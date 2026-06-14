"""Unit tests for ``SlurmEnvMetadataCollector``."""

from __future__ import annotations

import getpass
import os
from pathlib import Path

import pytest

from hpc_provenance.domain.enums import JobState, SchedulerType
from hpc_provenance.domain.exceptions import MetadataCollectionError
from hpc_provenance.domain.value_objects import JobIdentifier
from hpc_provenance.infrastructure.collectors.slurm_collector import SlurmEnvMetadataCollector


@pytest.fixture(autouse=True)
def clear_slurm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no stray ``SLURM_*`` variables leak in from the host environment."""
    for key in list(os.environ):
        if key.startswith("SLURM_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def slurm_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SLURM_JOB_ID", "123456")
    monkeypatch.setenv("SLURM_JOB_NAME", "train-model")
    monkeypatch.setenv("SLURM_JOB_PARTITION", "gpu")
    monkeypatch.setenv("SLURM_JOB_NODELIST", "node[01-02]")
    monkeypatch.setenv("SLURM_JOB_NUM_NODES", "2")
    monkeypatch.setenv("SLURM_NTASKS", "2")
    monkeypatch.setenv("SLURM_CPUS_PER_TASK", "8")
    monkeypatch.setenv("SLURM_GPUS_PER_NODE", "4")
    monkeypatch.setenv("SLURM_SUBMIT_DIR", str(tmp_path))
    monkeypatch.setenv("SLURM_JOB_ACCOUNT", "research")
    monkeypatch.setenv("SLURM_JOB_USER", "jdoe")


def test_collect_builds_metadata_from_environment(slurm_env: None, tmp_path: Path) -> None:
    collector = SlurmEnvMetadataCollector()

    metadata = collector.collect()

    assert metadata.job_id == JobIdentifier(scheduler=SchedulerType.SLURM, value="123456")
    assert metadata.job_name == "train-model"
    assert metadata.user_name == "jdoe"
    assert metadata.account == "research"
    assert metadata.state == JobState.RUNNING
    assert metadata.exit_code is None
    assert metadata.working_directory == Path(str(tmp_path))
    assert metadata.allocation.num_nodes == 2
    assert metadata.allocation.num_tasks == 2
    assert metadata.allocation.cpus_per_task == 8
    assert metadata.allocation.node_list == ("node01", "node02")
    assert metadata.allocation.partition == "gpu"
    assert metadata.allocation.gpus_per_node == 4
    assert metadata.execution_window.finished_at is None
    assert metadata.environment["SLURM_JOB_ID"] == "123456"


def test_collect_uses_explicit_job_id(slurm_env: None) -> None:
    collector = SlurmEnvMetadataCollector()
    job_id = JobIdentifier(scheduler=SchedulerType.SLURM, value="999", array_index="3")

    metadata = collector.collect(job_id)

    assert metadata.job_id == job_id


def test_collect_resolves_array_job_id(monkeypatch: pytest.MonkeyPatch, slurm_env: None) -> None:
    monkeypatch.setenv("SLURM_ARRAY_JOB_ID", "111")
    monkeypatch.setenv("SLURM_ARRAY_TASK_ID", "5")

    collector = SlurmEnvMetadataCollector()
    metadata = collector.collect()

    assert metadata.job_id == JobIdentifier(
        scheduler=SchedulerType.SLURM, value="111", array_index="5"
    )


def test_collect_falls_back_to_current_user(monkeypatch: pytest.MonkeyPatch, slurm_env: None) -> None:
    monkeypatch.delenv("SLURM_JOB_USER", raising=False)
    monkeypatch.delenv("USER", raising=False)
    monkeypatch.delenv("LOGNAME", raising=False)

    collector = SlurmEnvMetadataCollector()
    metadata = collector.collect()

    assert metadata.user_name == getpass.getuser()


def test_collect_raises_without_job_id() -> None:
    collector = SlurmEnvMetadataCollector()

    with pytest.raises(MetadataCollectionError):
        collector.collect()
