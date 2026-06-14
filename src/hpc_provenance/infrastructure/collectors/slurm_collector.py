"""Slurm-backed implementations of ``SchedulerMetadataCollector``."""

from __future__ import annotations

import getpass
import json
import os
import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path

from hpc_provenance.domain.enums import JobState, SchedulerType
from hpc_provenance.domain.exceptions import MetadataCollectionError
from hpc_provenance.domain.interfaces.collectors import SchedulerMetadataCollector
from hpc_provenance.domain.models.scheduler_metadata import (
    JobExecutionWindow,
    ResourceAllocation,
    SlurmJobMetadata,
)
from hpc_provenance.domain.value_objects import JobIdentifier

CommandRunner = Callable[[Sequence[str]], str]

_GPU_TRES_RE = re.compile(r"gres/gpu(?::[^=,]+)?=(\d+)")
_HOSTLIST_GROUP_RE = re.compile(r"^([^\[\]]*)(?:\[(.*)\])?$")

_JOB_STATE_MAP: Mapping[str, JobState] = {
    "PENDING": JobState.PENDING,
    "CONFIGURING": JobState.PENDING,
    "RUNNING": JobState.RUNNING,
    "COMPLETING": JobState.RUNNING,
    "COMPLETED": JobState.COMPLETED,
    "FAILED": JobState.FAILED,
    "NODE_FAIL": JobState.FAILED,
    "CANCELLED": JobState.CANCELLED,
    "PREEMPTED": JobState.CANCELLED,
    "TIMEOUT": JobState.TIMEOUT,
    "OUT_OF_MEMORY": JobState.OUT_OF_MEMORY,
}


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------


def _run_command(args: Sequence[str]) -> str:
    """Run ``args`` and return its captured stdout.

    Raises:
        MetadataCollectionError: if the executable cannot be found or exits
            with a non-zero status.
    """
    try:
        result = subprocess.run(args, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise MetadataCollectionError(f"command not found: {args[0]!r}") from exc

    if result.returncode != 0:
        raise MetadataCollectionError(
            f"command {' '.join(args)!r} exited with status {result.returncode}: "
            f"{result.stderr.strip()}"
        )
    return result.stdout


def _resolve_job_id(job_id: JobIdentifier | None) -> JobIdentifier:
    """Return ``job_id``, or resolve one from ``SLURM_*`` environment variables."""
    if job_id is not None:
        return job_id

    raw_id = os.environ.get("SLURM_ARRAY_JOB_ID") or os.environ.get("SLURM_JOB_ID")
    if raw_id is None:
        raise MetadataCollectionError(
            "no job_id provided and SLURM_JOB_ID is not set in the environment"
        )
    return JobIdentifier(
        scheduler=SchedulerType.SLURM,
        value=raw_id,
        array_index=os.environ.get("SLURM_ARRAY_TASK_ID"),
    )


def _job_id_for_cli(job_id: JobIdentifier) -> str:
    """Format ``job_id`` the way Slurm CLI tools expect (``<id>`` or ``<id>_<task>``)."""
    if job_id.array_index is None:
        return job_id.value
    return f"{job_id.value}_{job_id.array_index}"


def _expand_hostlist(nodelist: str, run: CommandRunner = _run_command) -> tuple[str, ...]:
    """Expand a Slurm hostlist expression (e.g. ``"node[01-03,05]"``) into
    individual host names.

    Prefers ``scontrol show hostnames``, which correctly handles every Slurm
    hostlist edge case; falls back to a pure-Python expansion of the common
    ``prefix[a-b,c,d-e]`` form if ``scontrol`` is unavailable.
    """
    nodelist = nodelist.strip()
    if not nodelist:
        return ()

    try:
        output = run(["scontrol", "show", "hostnames", nodelist])
        hosts = tuple(line.strip() for line in output.splitlines() if line.strip())
        if hosts:
            return hosts
    except MetadataCollectionError:
        pass

    return _expand_hostlist_fallback(nodelist)


def _expand_hostlist_fallback(nodelist: str) -> tuple[str, ...]:
    """Expand ``prefix[a-b,c,d-e]``-style hostlist groups without ``scontrol``."""
    hosts: list[str] = []
    for group in _split_top_level(nodelist):
        match = _HOSTLIST_GROUP_RE.match(group)
        if not match:
            hosts.append(group)
            continue
        prefix, ranges = match.groups()
        if ranges is None:
            hosts.append(prefix)
            continue
        for part in ranges.split(","):
            if "-" in part:
                start_str, end_str = part.split("-", 1)
                width = len(start_str)
                for value in range(int(start_str), int(end_str) + 1):
                    hosts.append(f"{prefix}{value:0{width}d}")
            else:
                hosts.append(f"{prefix}{part}")
    return tuple(hosts)


def _split_top_level(nodelist: str) -> list[str]:
    """Split ``nodelist`` on commas that are not nested inside ``[...]``."""
    groups: list[str] = []
    depth = 0
    current: list[str] = []
    for char in nodelist:
        if char == "[":
            depth += 1
            current.append(char)
        elif char == "]":
            depth -= 1
            current.append(char)
        elif char == "," and depth == 0:
            groups.append("".join(current))
            current = []
        else:
            current.append(char)
    if current:
        groups.append("".join(current))
    return groups


def _parse_gpu_count(value: str) -> int | None:
    """Parse a GPU count from a GRES-style value (``"4"``, ``"gpu:4"``, ``"gpu:a100:4"``)."""
    match = _GPU_TRES_RE.search(value)
    if match:
        return int(match.group(1))
    last_segment = value.rsplit(":", 1)[-1]
    return int(last_segment) if last_segment.isdigit() else None


def _epoch_to_datetime(value: object) -> datetime | None:
    """Convert a Slurm epoch-seconds timestamp to UTC. ``0``/missing means unset."""
    try:
        seconds = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(seconds, tz=timezone.utc) if seconds > 0 else None


def _int_or(value: object, default: int) -> int:
    """Coerce ``value`` to a positive ``int``, or return ``default``."""
    if isinstance(value, bool) or value is None:
        return default
    try:
        result = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return result if result > 0 else default


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


# --------------------------------------------------------------------------
# Env-based collector
# --------------------------------------------------------------------------


class SlurmEnvMetadataCollector(SchedulerMetadataCollector):
    """Reads job metadata from ``SLURM_*`` environment variables.

    Suitable for use *inside* a running job (e.g. invoked from a job script
    or epilog), where ``sacct``/``scontrol`` may not yet have final
    accounting data.
    """

    def collect(self, job_id: JobIdentifier | None = None) -> SlurmJobMetadata:
        """See ``SchedulerMetadataCollector.collect``."""
        resolved_id = _resolve_job_id(job_id)
        env = os.environ

        node_list = _expand_hostlist(env.get("SLURM_JOB_NODELIST", ""))
        allocation = ResourceAllocation(
            num_nodes=_int_or(
                env.get("SLURM_JOB_NUM_NODES") or env.get("SLURM_NNODES"),
                len(node_list) or 1,
            ),
            num_tasks=_int_or(env.get("SLURM_NTASKS") or env.get("SLURM_NPROCS"), 1),
            cpus_per_task=_int_or(env.get("SLURM_CPUS_PER_TASK"), 1),
            node_list=node_list,
            partition=env.get("SLURM_JOB_PARTITION", ""),
            gpus_per_node=_parse_gpu_count(
                env.get("SLURM_GPUS_PER_NODE") or env.get("SLURM_GPUS_ON_NODE") or ""
            ),
        )

        execution_window = JobExecutionWindow(
            submitted_at=_epoch_to_datetime(env.get("SLURM_JOB_SUBMIT_TIME")),
            started_at=_epoch_to_datetime(env.get("SLURM_JOB_START_TIME")),
            finished_at=None,
        )

        user_name = (
            env.get("SLURM_JOB_USER")
            or env.get("USER")
            or env.get("LOGNAME")
            or getpass.getuser()
        )

        return SlurmJobMetadata(
            job_id=resolved_id,
            job_name=env.get("SLURM_JOB_NAME", ""),
            user_name=user_name,
            account=_optional_str(env.get("SLURM_JOB_ACCOUNT")),
            state=JobState.RUNNING,
            exit_code=None,
            working_directory=Path(env.get("SLURM_SUBMIT_DIR", os.getcwd())),
            submit_command=(),
            environment={k: v for k, v in env.items() if k.startswith("SLURM_")},
            allocation=allocation,
            execution_window=execution_window,
        )


# --------------------------------------------------------------------------
# CLI-based collector
# --------------------------------------------------------------------------


class SlurmCliMetadataCollector(SchedulerMetadataCollector):
    """Reads job metadata via the Slurm CLI (``sacct``, ``scontrol show job``).

    Suitable for use *after* a job completes, where full accounting data
    (exit code, finish time, resource usage) is available.
    """

    def __init__(self, run: CommandRunner | None = None) -> None:
        """``run`` executes a command and returns its stdout; override for tests."""
        self._run = run or _run_command

    def collect(self, job_id: JobIdentifier | None = None) -> SlurmJobMetadata:
        """See ``SchedulerMetadataCollector.collect``."""
        resolved_id = _resolve_job_id(job_id)
        record = self._fetch_job_record(resolved_id)
        return self._build_job_metadata(resolved_id, record)

    def _fetch_job_record(self, job_id: JobIdentifier) -> Mapping[str, object]:
        cli_id = _job_id_for_cli(job_id)

        for args in (
            ["sacct", "-j", cli_id, "--json"],
            ["scontrol", "show", "job", cli_id, "--json"],
        ):
            try:
                payload = json.loads(self._run(args))
            except (MetadataCollectionError, json.JSONDecodeError):
                continue
            jobs = payload.get("jobs")
            if isinstance(jobs, list) and jobs:
                return jobs[0]

        raise MetadataCollectionError(
            f"no Slurm accounting record found for job {job_id} via sacct or scontrol"
        )

    def _build_job_metadata(
        self, job_id: JobIdentifier, record: Mapping[str, object]
    ) -> SlurmJobMetadata:
        """Build a ``SlurmJobMetadata`` from a single ``sacct``/``scontrol --json`` job record."""
        time_info = record.get("time")
        time_info = time_info if isinstance(time_info, Mapping) else {}

        node_list = _expand_hostlist(str(record.get("nodes") or ""), self._run)

        allocation = ResourceAllocation(
            num_nodes=_int_or(
                record.get("node_count")
                or record.get("allocation_nodes")
                or _tres_count(record, "node"),
                len(node_list) or 1,
            ),
            num_tasks=_int_or(record.get("tasks") or record.get("ntasks"), 1),
            cpus_per_task=_int_or(record.get("cpus_per_task"), _derive_cpus_per_task(record)),
            node_list=node_list,
            partition=str(record.get("partition") or ""),
            gpus_per_node=_extract_gpu_count(record),
        )

        execution_window = JobExecutionWindow(
            submitted_at=_epoch_to_datetime(
                time_info.get("submission") or record.get("submit_time")
            ),
            started_at=_epoch_to_datetime(time_info.get("start") or record.get("start_time")),
            finished_at=_epoch_to_datetime(time_info.get("end") or record.get("end_time")),
        )

        working_directory = (
            record.get("working_directory")
            or record.get("current_working_directory")
            or record.get("work_dir")
            or "."
        )

        return SlurmJobMetadata(
            job_id=job_id,
            job_name=str(record.get("name") or record.get("job_name") or ""),
            user_name=str(record.get("user") or record.get("user_name") or ""),
            account=_optional_str(record.get("account")),
            state=_map_job_state(_extract_state(record)),
            exit_code=_extract_exit_code(record),
            working_directory=Path(str(working_directory)),
            submit_command=_extract_submit_command(record),
            environment={},
            allocation=allocation,
            execution_window=execution_window,
        )


# --------------------------------------------------------------------------
# sacct / scontrol record parsing helpers
# --------------------------------------------------------------------------


def _tres_count(record: Mapping[str, object], tres_type: str) -> int | None:
    """Read an allocated TRES count (e.g. ``node``, ``cpu``) from ``sacct --json``."""
    tres = record.get("tres")
    if not isinstance(tres, Mapping):
        return None
    for item in tres.get("allocated", []) or []:
        if isinstance(item, Mapping) and item.get("type") == tres_type:
            count = item.get("count")
            if isinstance(count, int):
                return count
    return None


def _derive_cpus_per_task(record: Mapping[str, object]) -> int:
    """Estimate ``cpus_per_task`` from total allocated CPUs when not reported directly."""
    total_cpus = _tres_count(record, "cpu")
    num_tasks = _int_or(record.get("tasks") or record.get("ntasks"), 1)
    if total_cpus:
        return max(total_cpus // num_tasks, 1)
    return 1


def _extract_gpu_count(record: Mapping[str, object]) -> int | None:
    tres = record.get("tres")
    if isinstance(tres, Mapping):
        for item in tres.get("allocated", []) or []:
            if (
                isinstance(item, Mapping)
                and item.get("type") == "gres"
                and item.get("name") == "gpu"
            ):
                allocated = item.get("count")
                if isinstance(allocated, int):
                    return allocated

    for key in ("tres_alloc_str", "tres_per_node", "gres_detail", "gres"):
        value = record.get(key)
        candidates = value if isinstance(value, list) else [value]
        for candidate in candidates:
            if isinstance(candidate, str) and "gpu" in candidate.lower():
                parsed = _parse_gpu_count(candidate)
                if parsed is not None:
                    return parsed
    return None


def _extract_state(record: Mapping[str, object]) -> object:
    state = record.get("state")
    if isinstance(state, Mapping):
        return state.get("current")
    return state if state is not None else record.get("job_state")


def _map_job_state(raw: object) -> JobState:
    if isinstance(raw, str):
        candidates: Sequence[str] = (raw,)
    elif isinstance(raw, (list, tuple)):
        candidates = tuple(str(item) for item in raw)
    else:
        candidates = ()

    for candidate in candidates:
        # sacct sometimes appends details, e.g. "CANCELLED by 1000".
        token = candidate.split()[0] if candidate.split() else candidate
        mapped = _JOB_STATE_MAP.get(token.upper())
        if mapped is not None:
            return mapped
    return JobState.UNKNOWN


def _extract_exit_code(record: Mapping[str, object]) -> int | None:
    for key in ("exit_code", "derived_exit_code"):
        value = record.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, Mapping):
            return_code = value.get("return_code")
            if isinstance(return_code, Mapping):
                number = return_code.get("number")
                if isinstance(number, int):
                    return number
            elif isinstance(return_code, int):
                return return_code
    return None


def _extract_submit_command(record: Mapping[str, object]) -> tuple[str, ...]:
    for key in ("submit_line", "command", "batch_script"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return tuple(value.split())
    return ()
