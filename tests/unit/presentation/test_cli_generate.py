"""Unit tests for the ``hpc-provenance generate run`` CLI command."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hpc_provenance.domain.exceptions import MetadataCollectionError
from hpc_provenance.infrastructure.collectors import slurm_collector
from hpc_provenance.presentation.cli.app import app

runner = CliRunner()

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
            },
            "tres": {
                "allocated": [
                    {"type": "cpu", "name": None, "id": 1, "count": 16},
                    {"type": "node", "name": None, "id": 2, "count": 2},
                    {"type": "gres", "name": "gpu", "id": 1001, "count": 4},
                ]
            },
            "submit_line": "sbatch train.slurm --epochs 10",
        }
    ]
}


def _fake_run(args: Sequence[str]) -> str:
    if args[0] == "sacct":
        return json.dumps(SACCT_PAYLOAD)
    if args[:3] == ["scontrol", "show", "hostnames"]:
        return "node01\nnode02\n"
    raise MetadataCollectionError(f"unexpected command: {args}")


@pytest.fixture(autouse=True)
def _fake_slurm_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(slurm_collector, "_run_command", _fake_run)
    monkeypatch.setenv("SLURM_JOB_ID", "123456")
    monkeypatch.delenv("SLURM_ARRAY_JOB_ID", raising=False)
    monkeypatch.delenv("SLURM_ARRAY_TASK_ID", raising=False)


def test_generate_run_writes_statement_to_output_file(tmp_path: Path) -> None:
    product = tmp_path / "model.safetensors"
    product.write_bytes(b"model weights")
    output = tmp_path / "statement.json"

    result = runner.invoke(
        app,
        [
            "generate",
            "run",
            "--product",
            str(product),
            "--builder-id",
            "https://example.org/hpc-provenance/builder/v1",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    statement = json.loads(output.read_text())
    assert statement["predicateType"] == "https://slsa.dev/provenance/v1"
    assert statement["subject"][0]["name"] == "model.safetensors"
    assert statement["predicate"]["buildDefinition"]["internalParameters"]["jobId"] == "slurm:123456"


def test_generate_run_writes_statement_to_stdout(tmp_path: Path) -> None:
    product = tmp_path / "model.safetensors"
    product.write_bytes(b"model weights")

    result = runner.invoke(
        app,
        [
            "generate",
            "run",
            "--product",
            str(product),
            "--builder-id",
            "https://example.org/hpc-provenance/builder/v1",
        ],
    )

    assert result.exit_code == 0, result.output
    statement = json.loads(result.output)
    assert statement["predicateType"] == "https://slsa.dev/provenance/v1"
