"""Unit tests for the pure-function helpers used by the Slurm collectors."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hpc_provenance.domain.enums import JobState
from hpc_provenance.domain.exceptions import MetadataCollectionError
from hpc_provenance.domain.models.scheduler_metadata import ResourceUsage
from hpc_provenance.infrastructure.collectors.slurm_collector import (
    _cpu_time_seconds,
    _epoch_to_datetime,
    _expand_hostlist,
    _expand_hostlist_fallback,
    _extract_resource_usage,
    _int_or,
    _map_job_state,
    _max_consumed_tres_bytes,
    _non_negative_float,
    _parse_gpu_count,
    _run_command,
    _seconds_with_microseconds,
)


@pytest.mark.parametrize(
    ("nodelist", "expected"),
    [
        ("", ()),
        ("node01", ("node01",)),
        ("node[01-03]", ("node01", "node02", "node03")),
        ("node[01-03,05]", ("node01", "node02", "node03", "node05")),
        ("nodeA,nodeB", ("nodeA", "nodeB")),
        ("node[1-2],gpu[01-02]", ("node1", "node2", "gpu01", "gpu02")),
    ],
)
def test_expand_hostlist_fallback(nodelist: str, expected: tuple[str, ...]) -> None:
    assert _expand_hostlist_fallback(nodelist) == expected


def test_expand_hostlist_prefers_scontrol_output() -> None:
    def run(args: object) -> str:
        assert args == ["scontrol", "show", "hostnames", "node[01-02]"]
        return "node01\nnode02\n"

    assert _expand_hostlist("node[01-02]", run) == ("node01", "node02")


def test_expand_hostlist_falls_back_when_scontrol_unavailable() -> None:
    def run(args: object) -> str:
        raise MetadataCollectionError("scontrol not found")

    assert _expand_hostlist("node[01-02]", run) == ("node01", "node02")


def test_expand_hostlist_empty_returns_empty_tuple() -> None:
    assert _expand_hostlist("") == ()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("4", 4),
        ("gpu:4", 4),
        ("gpu:a100:4", 4),
        ("gres/gpu=2", 2),
        ("gres/gpu:a100=8", 8),
        ("", None),
        ("gpu", None),
    ],
)
def test_parse_gpu_count(value: str, expected: int | None) -> None:
    assert _parse_gpu_count(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        (0, None),
        ("0", None),
        (1750000000, datetime.fromtimestamp(1750000000, tz=timezone.utc)),
        ("1750000000", datetime.fromtimestamp(1750000000, tz=timezone.utc)),
        ("not-a-number", None),
    ],
)
def test_epoch_to_datetime(value: object, expected: datetime | None) -> None:
    assert _epoch_to_datetime(value) == expected


@pytest.mark.parametrize(
    ("value", "default", "expected"),
    [
        (None, 1, 1),
        ("4", 1, 4),
        (4, 1, 4),
        ("0", 1, 1),
        ("not-a-number", 2, 2),
        (True, 1, 1),
    ],
)
def test_int_or(value: object, default: int, expected: int) -> None:
    assert _int_or(value, default) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("COMPLETED", JobState.COMPLETED),
        (["RUNNING"], JobState.RUNNING),
        (["CANCELLED by 1000"], JobState.CANCELLED),
        ("OUT_OF_MEMORY", JobState.OUT_OF_MEMORY),
        (None, JobState.UNKNOWN),
        ([], JobState.UNKNOWN),
    ],
)
def test_map_job_state(raw: object, expected: JobState) -> None:
    assert _map_job_state(raw) == expected


def test_run_command_raises_for_missing_executable() -> None:
    with pytest.raises(MetadataCollectionError):
        _run_command(["definitely-not-a-real-slurm-command"])


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        (5, 5.0),
        (5.5, 5.5),
        (0, 0.0),
        (-1, None),
        (True, None),
        ("5", None),
    ],
)
def test_non_negative_float(value: object, expected: float | None) -> None:
    assert _non_negative_float(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({"seconds": 10, "microseconds": 500000}, 10.5),
        ({"seconds": 10}, 10.0),
        ({}, None),
        (None, None),
        ("not-a-mapping", None),
    ],
)
def test_seconds_with_microseconds(value: object, expected: float | None) -> None:
    assert _seconds_with_microseconds(value) == expected


@pytest.mark.parametrize(
    ("time_info", "expected"),
    [
        ({"total_cpu": {"seconds": 100, "microseconds": 0}}, 100.0),
        ({"user": {"seconds": 60}, "system": {"seconds": 10}}, 70.0),
        ({"user": {"seconds": 60}}, 60.0),
        ({}, None),
    ],
)
def test_cpu_time_seconds(time_info: dict, expected: float | None) -> None:
    assert _cpu_time_seconds(time_info) == expected


def test_max_consumed_tres_bytes_returns_max_across_steps() -> None:
    record = {
        "steps": [
            {"tres": {"consumed": [{"type": "mem", "count": 1024}]}},
            {"tres": {"consumed": [{"type": "mem", "count": 2048}]}},
        ]
    }

    assert _max_consumed_tres_bytes(record, "mem") == 2048


@pytest.mark.parametrize(
    "record",
    [
        {},
        {"steps": []},
        {"steps": [{"tres": {}}]},
        {"steps": [{"tres": {"consumed": [{"type": "vmem", "count": 1024}]}}]},
    ],
)
def test_max_consumed_tres_bytes_returns_none_when_absent(record: dict) -> None:
    assert _max_consumed_tres_bytes(record, "mem") is None


def test_extract_resource_usage_parses_full_record() -> None:
    record = {
        "time": {
            "elapsed": 500,
            "total_cpu": {"seconds": 3600, "microseconds": 500000},
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
    }

    assert _extract_resource_usage(record) == ResourceUsage(
        elapsed_seconds=500.0,
        cpu_time_seconds=3600.5,
        max_rss_bytes=2147483648,
        max_vm_size_bytes=4294967296,
    )


def test_extract_resource_usage_returns_none_when_absent() -> None:
    assert _extract_resource_usage({}) is None
