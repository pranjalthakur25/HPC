"""Unit tests for the ``hpc-provenance verify attestation`` CLI command."""

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


def _statement_path(tmp_path: Path) -> Path:
    statement = InTotoStatement(
        subjects=(ResourceDescriptor(name="model.safetensors", digest={"sha256": "b" * 64}),),
        predicate_type="https://slsa.dev/provenance/v1",
        predicate={"buildDefinition": {}, "runDetails": {}},
    )
    path = tmp_path / "statement.json"
    path.write_text(statement.to_json())
    return path


def _generate_key(tmp_path: Path, key_id: str) -> Path:
    keys_dir = tmp_path / "keys"
    result = runner.invoke(app, ["keys", "generate", key_id, "--keys-dir", str(keys_dir)])
    assert result.exit_code == 0, result.output
    return keys_dir


def _sign(tmp_path: Path, statement_path: Path, key_id: str) -> Path:
    envelope_path = tmp_path / "attestation.dsse"
    result = runner.invoke(
        app,
        ["sign", "run", str(statement_path), "--key-id", key_id, "--output", str(envelope_path)],
    )
    assert result.exit_code == 0, result.output
    return envelope_path


def test_verify_attestation_valid_envelope(tmp_path: Path) -> None:
    _generate_key(tmp_path, "cluster-key-1")
    envelope_path = _sign(tmp_path, _statement_path(tmp_path), "cluster-key-1")

    result = runner.invoke(
        app, ["verify", "attestation", str(envelope_path), "--trusted-key-id", "cluster-key-1"]
    )

    assert result.exit_code == 0, result.output
    assert "VALID" in result.output


def test_verify_attestation_untrusted_key_is_invalid(tmp_path: Path) -> None:
    _generate_key(tmp_path, "cluster-key-1")
    envelope_path = _sign(tmp_path, _statement_path(tmp_path), "cluster-key-1")

    result = runner.invoke(
        app, ["verify", "attestation", str(envelope_path), "--trusted-key-id", "some-other-key"]
    )

    assert result.exit_code == 1
    assert "INVALID" in result.output


def test_verify_attestation_tampered_signature_is_invalid(tmp_path: Path) -> None:
    _generate_key(tmp_path, "cluster-key-1")
    envelope_path = _sign(tmp_path, _statement_path(tmp_path), "cluster-key-1")

    envelope = json.loads(envelope_path.read_text())
    sig = envelope["signatures"][0]["sig"]
    envelope["signatures"][0]["sig"] = sig[:-4] + ("AAAA" if sig[-4:] != "AAAA" else "BBBB")
    envelope_path.write_text(json.dumps(envelope))

    result = runner.invoke(
        app, ["verify", "attestation", str(envelope_path), "--trusted-key-id", "cluster-key-1"]
    )

    assert result.exit_code == 1
    assert "INVALID" in result.output
