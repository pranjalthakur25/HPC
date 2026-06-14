"""Unit tests for the ``hpc-provenance sign run`` CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hpc_provenance.domain.models.in_toto import InTotoStatement
from hpc_provenance.domain.models.provenance import ResourceDescriptor
from hpc_provenance.presentation.cli.app import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _settings_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HPC_PROVENANCE_KEYS_DIRECTORY", str(tmp_path / "keys"))
    monkeypatch.setenv("HPC_PROVENANCE_OUTPUT_DIRECTORY", str(tmp_path / "provenance"))


def _write_statement(path: Path) -> None:
    statement = InTotoStatement(
        subjects=(ResourceDescriptor(name="model.safetensors", digest={"sha256": "b" * 64}),),
        predicate_type="https://slsa.dev/provenance/v1",
        predicate={"buildDefinition": {}, "runDetails": {}},
    )
    path.write_text(statement.to_json())


def test_sign_run_writes_envelope_to_output_file(tmp_path: Path) -> None:
    keys_dir = tmp_path / "keys"
    generate_result = runner.invoke(app, ["keys", "generate", "cluster-key-1", "--keys-dir", str(keys_dir)])
    assert generate_result.exit_code == 0, generate_result.output

    statement_path = tmp_path / "statement.json"
    _write_statement(statement_path)
    envelope_path = tmp_path / "attestation.dsse"

    result = runner.invoke(
        app,
        [
            "sign",
            "run",
            str(statement_path),
            "--key-id",
            "cluster-key-1",
            "--output",
            str(envelope_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "record id:" in result.output

    envelope = json.loads(envelope_path.read_text())
    assert envelope["payloadType"] == "application/vnd.in-toto+json"
    assert len(envelope["signatures"]) == 1
    assert envelope["signatures"][0]["keyid"] == "cluster-key-1"


def test_sign_run_writes_envelope_to_stdout(tmp_path: Path) -> None:
    keys_dir = tmp_path / "keys"
    generate_result = runner.invoke(app, ["keys", "generate", "cluster-key-1", "--keys-dir", str(keys_dir)])
    assert generate_result.exit_code == 0, generate_result.output

    statement_path = tmp_path / "statement.json"
    _write_statement(statement_path)

    result = runner.invoke(
        app,
        ["sign", "run", str(statement_path), "--key-id", "cluster-key-1"],
    )

    assert result.exit_code == 0, result.output
    assert "record id:" in result.output

    envelope_json, _, _ = result.output.rpartition("record id:")
    envelope = json.loads(envelope_json)
    assert envelope["payloadType"] == "application/vnd.in-toto+json"
