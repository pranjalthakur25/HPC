"""Unit tests for the ``hpc-provenance slurm prologue``/``epilogue`` CLI
commands, exercising a full prologue -> epilogue -> verify round trip.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hpc_provenance.presentation.cli.app import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _slurm_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("SLURM_"):
            monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("SLURM_JOB_ID", "123456")
    monkeypatch.setenv("SLURM_JOB_USER", "jdoe")
    monkeypatch.setenv("SLURM_JOB_NODELIST", "node01")
    monkeypatch.setenv("SLURM_JOB_PARTITION", "gpu")
    monkeypatch.setenv("SLURM_SUBMIT_DIR", str(tmp_path))

    monkeypatch.setenv("HPC_PROVENANCE_KEYS_DIRECTORY", str(tmp_path / "keys"))
    monkeypatch.setenv("HPC_PROVENANCE_OUTPUT_DIRECTORY", str(tmp_path / "provenance"))


def test_prologue_epilogue_verify_round_trip(tmp_path: Path) -> None:
    keys_dir = tmp_path / "keys"
    generate_result = runner.invoke(
        app, ["keys", "generate", "cluster-key-1", "--keys-dir", str(keys_dir)]
    )
    assert generate_result.exit_code == 0, generate_result.output

    prologue_result = runner.invoke(
        app, ["slurm", "prologue", "--output-dir", str(tmp_path)]
    )
    assert prologue_result.exit_code == 0, prologue_result.output

    prologue_snapshot = json.loads((tmp_path / "prologue.json").read_text())
    assert prologue_snapshot["jobId"] == "slurm:123456"
    assert prologue_snapshot["user"] == "jdoe"
    assert prologue_snapshot["partition"] == "gpu"

    product = tmp_path / "model.bin"
    product.write_bytes(b"model weights")

    epilogue_result = runner.invoke(
        app,
        [
            "slurm",
            "epilogue",
            "--product",
            str(product),
            "--key-id",
            "cluster-key-1",
            "--output-dir",
            str(tmp_path),
        ],
    )
    assert epilogue_result.exit_code == 0, epilogue_result.output
    assert "record id:" in epilogue_result.output

    statement_path = tmp_path / "provenance.json"
    attestation_path = tmp_path / "attestation.dsse"
    assert statement_path.is_file()
    assert attestation_path.is_file()

    statement = json.loads(statement_path.read_text())
    assert statement["predicate"]["buildDefinition"]["internalParameters"]["jobId"] == "slurm:123456"

    verify_result = runner.invoke(
        app,
        [
            "verify",
            "attestation",
            str(attestation_path),
            "--trusted-key-id",
            "cluster-key-1",
        ],
    )

    assert verify_result.exit_code == 0, verify_result.output
    assert "VALID" in verify_result.output
