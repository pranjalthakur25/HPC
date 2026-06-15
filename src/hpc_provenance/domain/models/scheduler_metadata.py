"""Domain models describing the HPC scheduler's view of a job.

Named for Slurm (the phase-1 target) but deliberately scheduler-agnostic in
shape: ``ResourceAllocation`` and ``JobExecutionWindow`` model concepts
present in most batch schedulers (PBS, LSF, ...). Scheduler-specific fields
should be added as additional *optional* fields rather than new ports.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from hpc_provenance.domain.enums import JobState
from hpc_provenance.domain.value_objects import JobIdentifier


@dataclass(frozen=True, slots=True)
class ResourceAllocation:
    """The compute resources allocated to a job."""

    num_nodes: int
    num_tasks: int
    cpus_per_task: int
    node_list: tuple[str, ...]
    partition: str
    gpus_per_node: int | None = None


@dataclass(frozen=True, slots=True)
class JobExecutionWindow:
    """The lifecycle timestamps of a job, as reported by the scheduler."""

    submitted_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class ResourceUsage:
    """Runtime resource-usage metrics for a completed job, as reported by
    ``sacct``.

    All fields are ``None`` when the underlying accounting data was not
    available (e.g. cgroup accounting disabled, or the job was collected via
    ``scontrol`` rather than ``sacct``).
    """

    elapsed_seconds: float | None = None
    cpu_time_seconds: float | None = None
    max_rss_bytes: int | None = None
    max_vm_size_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class SlurmJobMetadata:
    """Everything the system knows about a job from the scheduler's
    perspective. Feeds the ``BuilderIdentity``/``RunDetails`` portion of the
    eventual SLSA predicate.
    """

    job_id: JobIdentifier
    job_name: str
    user_name: str
    account: str | None
    state: JobState
    exit_code: int | None
    working_directory: Path
    submit_command: tuple[str, ...]
    environment: Mapping[str, str]
    allocation: ResourceAllocation
    execution_window: JobExecutionWindow
    resource_usage: ResourceUsage | None = None
