"""Unit tests for ``SlurmCliMetadataCollector`` using an injected command runner."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hpc_provenance.domain.enums import JobState, SchedulerType
from hpc_provenance.domain.exceptions import MetadataCollectionError
from hpc_provenance.domain.models.scheduler_metadata import ResourceUsage
from hpc_provenance.domain.value_objects import JobIdentifier
from hpc_provenance.infrastructure.collectors.slurm_collector import SlurmCliMetadataCollector

SACCT_PAYLOAD = {
    "jobs": [
        {
            "account": "research",
            "job_id": 123456,
            "name": "train-model",
            "user": "jdoe",
            "partition": "gpu",
            "nodes": "node[01-02]",
            "node_count": 2,
            "tasks": 2,
            "cpus_per_task": 8,
            "working_directory": "/home/jdoe/project",
            "exit_code": {
                "status": ["SUCCESS"],
                "return_code": {"set": True, "infinite": False, "number": 0},
            },
            "state": {"current": ["COMPLETED"]},
            "time": {
                "submission": 1750000000,
                "start": 1750000100,
                "end": 1750000600,
                "elapsed": 500,
                "total_cpu": {"seconds": 3600, "microseconds": 500000},
            },
            "tres": {
                "allocated": [
                    {"type": "cpu", "name": None, "id": 1, "count": 16},
                    {"type": "node", "name": None, "id": 2, "count": 2},
                    {"type": "gres", "name": "gpu", "id": 1001, "count": 4},
                ]
            },
            "steps": [
                {
                    "tres": {
                        "consumed": [
                            {"type": "mem", "count": 2147483648},
                            {"type": "vmem", "count": 4294967296},
                        ]
                    }
                }
            ],
            "submit_line": "sbatch train.slurm --epochs 10",
        }
    ]
}

SCONTROL_PAYLOAD = {
    "jobs": [
        {
            "account": "research",
            "job_id": 654321,
            "name": "infer-job",
            "user_name": "asmith",
            "job_state": ["RUNNING"],
            "partition": "cpu",
            "nodes": "cnode1",
            "node_count": 1,
            "cpus_per_task": 4,
            "current_working_directory": "/scratch/asmith/run",
            "submit_time": 1750100000,
            "start_time": 1750100100,
            "end_time": 0,
            "command": "/scratch/asmith/run/job.sh",
            "exit_code": 0,
            "tres_alloc_str": "cpu=4,mem=16G,node=1,billing=4,gres/gpu=1",
        }
    ]
}


def _sacct_and_hostnames_runner(payload: dict, hostnames: str) -> Callable[[Sequence[str]], str]:
    def run(args: Sequence[str]) -> str:
        if args[0] == "sacct":
            return json.dumps(payload)
        if args[:3] == ["scontrol", "show", "hostnames"]:
            return hostnames
        raise MetadataCollectionError(f"unexpected command: {args}")

    return run


def test_collect_parses_sacct_json() -> None:
    run = _sacct_and_hostnames_runner(SACCT_PAYLOAD, "node01\nnode02\n")
    collector = SlurmCliMetadataCollector(run=run)
    job_id = JobIdentifier(scheduler=SchedulerType.SLURM, value="123456")

    metadata = collector.collect(job_id)

    assert metadata.job_id == job_id
    assert metadata.job_name == "train-model"
    assert metadata.user_name == "jdoe"
    assert metadata.account == "research"
    assert metadata.state == JobState.COMPLETED
    assert metadata.exit_code == 0
    assert metadata.working_directory == Path("/home/jdoe/project")
    assert metadata.allocation.num_nodes == 2
    assert metadata.allocation.num_tasks == 2
    assert metadata.allocation.cpus_per_task == 8
    assert metadata.allocation.node_list == ("node01", "node02")
    assert metadata.allocation.partition == "gpu"
    assert metadata.allocation.gpus_per_node == 4
    assert metadata.submit_command == ("sbatch", "train.slurm", "--epochs", "10")
    assert metadata.execution_window.submitted_at == datetime.fromtimestamp(
        1750000000, tz=timezone.utc
    )
    assert metadata.execution_window.started_at == datetime.fromtimestamp(
        1750000100, tz=timezone.utc
    )
    assert metadata.execution_window.finished_at == datetime.fromtimestamp(
        1750000600, tz=timezone.utc
    )
    assert metadata.resource_usage == ResourceUsage(
        elapsed_seconds=500.0,
        cpu_time_seconds=3600.5,
        max_rss_bytes=2147483648,
        max_vm_size_bytes=4294967296,
    )


def test_collect_falls_back_to_scontrol_when_sacct_unavailable() -> None:
    def run(args: Sequence[str]) -> str:
        if args[0] == "sacct":
            raise MetadataCollectionError("sacct: command not found")
        if args[:3] == ["scontrol", "show", "job"]:
            return json.dumps(SCONTROL_PAYLOAD)
        if args[:3] == ["scontrol", "show", "hostnames"]:
            return "cnode1\n"
        raise MetadataCollectionError(f"unexpected command: {args}")

    collector = SlurmCliMetadataCollector(run=run)
    job_id = JobIdentifier(scheduler=SchedulerType.SLURM, value="654321")

    metadata = collector.collect(job_id)

    assert metadata.user_name == "asmith"
    assert metadata.state == JobState.RUNNING
    assert metadata.exit_code == 0
    assert metadata.working_directory == Path("/scratch/asmith/run")
    assert metadata.allocation.node_list == ("cnode1",)
    assert metadata.allocation.gpus_per_node == 1
    assert metadata.allocation.cpus_per_task == 4
    assert metadata.submit_command == ("/scratch/asmith/run/job.sh",)
    assert metadata.execution_window.finished_at is None
    assert metadata.resource_usage is None


def test_collect_resolves_job_id_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLURM_JOB_ID", "123456")
    monkeypatch.delenv("SLURM_ARRAY_JOB_ID", raising=False)
    monkeypatch.delenv("SLURM_ARRAY_TASK_ID", raising=False)

    def run(args: Sequence[str]) -> str:
        if args[0] == "sacct":
            assert args[2] == "123456"
            return json.dumps(SACCT_PAYLOAD)
        if args[:3] == ["scontrol", "show", "hostnames"]:
            return "node01\nnode02\n"
        raise MetadataCollectionError(f"unexpected command: {args}")

    collector = SlurmCliMetadataCollector(run=run)

    metadata = collector.collect()

    assert metadata.job_id == JobIdentifier(scheduler=SchedulerType.SLURM, value="123456")


def test_collect_raises_when_no_record_found() -> None:
    def run(args: Sequence[str]) -> str:
        raise MetadataCollectionError("not found")

    collector = SlurmCliMetadataCollector(run=run)
    job_id = JobIdentifier(scheduler=SchedulerType.SLURM, value="000")

    with pytest.raises(MetadataCollectionError):
        collector.collect(job_id)
