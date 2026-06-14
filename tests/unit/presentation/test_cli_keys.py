"""Unit tests for the ``hpc-provenance keys`` CLI command group."""

from __future__ import annotations

from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from typer.testing import CliRunner

from hpc_provenance.presentation.cli.app import app

runner = CliRunner()


def test_generate_writes_ecdsa_key_pair_by_default(tmp_path: Path) -> None:
    keys_dir = tmp_path / "keys"

    result = runner.invoke(app, ["keys", "generate", "cluster-key-1", "--keys-dir", str(keys_dir)])

    assert result.exit_code == 0, result.output
    private_pem = (keys_dir / "cluster-key-1.private.pem").read_bytes()
    public_pem = (keys_dir / "cluster-key-1.public.pem").read_bytes()

    private_key = serialization.load_pem_private_key(private_pem, password=None)
    public_key = serialization.load_pem_public_key(public_pem)
    assert isinstance(private_key, ec.EllipticCurvePrivateKey)
    assert isinstance(public_key, ec.EllipticCurvePublicKey)


def test_generate_writes_rsa_key_pair_when_requested(tmp_path: Path) -> None:
    keys_dir = tmp_path / "keys"

    result = runner.invoke(
        app,
        ["keys", "generate", "cluster-key-1", "--algorithm", "rsa", "--keys-dir", str(keys_dir)],
    )

    assert result.exit_code == 0, result.output
    private_pem = (keys_dir / "cluster-key-1.private.pem").read_bytes()
    public_pem = (keys_dir / "cluster-key-1.public.pem").read_bytes()

    private_key = serialization.load_pem_private_key(private_pem, password=None)
    public_key = serialization.load_pem_public_key(public_pem)
    assert isinstance(private_key, rsa.RSAPrivateKey)
    assert isinstance(public_key, rsa.RSAPublicKey)


def test_generate_creates_keys_directory_if_missing(tmp_path: Path) -> None:
    keys_dir = tmp_path / "nested" / "keys"

    result = runner.invoke(app, ["keys", "generate", "cluster-key-1", "--keys-dir", str(keys_dir)])

    assert result.exit_code == 0, result.output
    assert keys_dir.is_dir()
