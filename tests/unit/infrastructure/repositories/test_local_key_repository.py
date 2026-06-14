"""Unit tests for ``LocalFileKeyRepository``."""

from __future__ import annotations

from pathlib import Path

import pytest

from hpc_provenance.domain.exceptions import SigningError, VerificationError
from hpc_provenance.domain.value_objects import SigningKey, VerificationKey
from hpc_provenance.infrastructure.repositories.local_key_repository import LocalFileKeyRepository


def _write_key_pair(keys_dir: Path, key_id: str, key_pair: tuple[SigningKey, VerificationKey]) -> None:
    signing_key, verification_key = key_pair
    (keys_dir / f"{key_id}.private.pem").write_bytes(signing_key.private_key_material)
    (keys_dir / f"{key_id}.public.pem").write_bytes(verification_key.public_key_material)


def test_get_signing_key_detects_rsa_algorithm(
    tmp_path: Path, rsa_key_pair: tuple[SigningKey, VerificationKey]
) -> None:
    _write_key_pair(tmp_path, "rsa-key-1", rsa_key_pair)
    repository = LocalFileKeyRepository(keys_directory=tmp_path)

    signing_key = repository.get_signing_key("rsa-key-1")

    assert signing_key.key_id == "rsa-key-1"
    assert signing_key.algorithm == "rsa"
    assert signing_key.private_key_material == rsa_key_pair[0].private_key_material


def test_get_signing_key_detects_ecdsa_algorithm(
    tmp_path: Path, ec_key_pair: tuple[SigningKey, VerificationKey]
) -> None:
    _write_key_pair(tmp_path, "ec-key-1", ec_key_pair)
    repository = LocalFileKeyRepository(keys_directory=tmp_path)

    signing_key = repository.get_signing_key("ec-key-1")

    assert signing_key.algorithm == "ecdsa"


def test_get_verification_key_detects_rsa_algorithm(
    tmp_path: Path, rsa_key_pair: tuple[SigningKey, VerificationKey]
) -> None:
    _write_key_pair(tmp_path, "rsa-key-1", rsa_key_pair)
    repository = LocalFileKeyRepository(keys_directory=tmp_path)

    verification_key = repository.get_verification_key("rsa-key-1")

    assert verification_key.key_id == "rsa-key-1"
    assert verification_key.algorithm == "rsa"
    assert verification_key.public_key_material == rsa_key_pair[1].public_key_material


def test_get_verification_key_detects_ecdsa_algorithm(
    tmp_path: Path, ec_key_pair: tuple[SigningKey, VerificationKey]
) -> None:
    _write_key_pair(tmp_path, "ec-key-1", ec_key_pair)
    repository = LocalFileKeyRepository(keys_directory=tmp_path)

    verification_key = repository.get_verification_key("ec-key-1")

    assert verification_key.algorithm == "ecdsa"


def test_get_signing_key_raises_signing_error_when_missing(tmp_path: Path) -> None:
    repository = LocalFileKeyRepository(keys_directory=tmp_path)

    with pytest.raises(SigningError):
        repository.get_signing_key("missing-key")


def test_get_verification_key_raises_verification_error_when_missing(tmp_path: Path) -> None:
    repository = LocalFileKeyRepository(keys_directory=tmp_path)

    with pytest.raises(VerificationError):
        repository.get_verification_key("missing-key")


def test_get_signing_key_raises_signing_error_for_invalid_pem(tmp_path: Path) -> None:
    (tmp_path / "bad-key.private.pem").write_bytes(b"not a pem")
    repository = LocalFileKeyRepository(keys_directory=tmp_path)

    with pytest.raises(SigningError):
        repository.get_signing_key("bad-key")


def test_get_verification_key_raises_verification_error_for_invalid_pem(tmp_path: Path) -> None:
    (tmp_path / "bad-key.public.pem").write_bytes(b"not a pem")
    repository = LocalFileKeyRepository(keys_directory=tmp_path)

    with pytest.raises(VerificationError):
        repository.get_verification_key("bad-key")


def test_trusted_key_ids_returns_all_public_keys(
    tmp_path: Path,
    rsa_key_pair: tuple[SigningKey, VerificationKey],
    ec_key_pair: tuple[SigningKey, VerificationKey],
) -> None:
    _write_key_pair(tmp_path, "rsa-key-1", rsa_key_pair)
    _write_key_pair(tmp_path, "ec-key-1", ec_key_pair)
    repository = LocalFileKeyRepository(keys_directory=tmp_path)

    assert repository.trusted_key_ids() == {"rsa-key-1", "ec-key-1"}


def test_trusted_key_ids_returns_empty_for_missing_directory(tmp_path: Path) -> None:
    repository = LocalFileKeyRepository(keys_directory=tmp_path / "does-not-exist")

    assert repository.trusted_key_ids() == frozenset()


def test_trusted_key_ids_applies_override(
    tmp_path: Path,
    rsa_key_pair: tuple[SigningKey, VerificationKey],
    ec_key_pair: tuple[SigningKey, VerificationKey],
) -> None:
    _write_key_pair(tmp_path, "rsa-key-1", rsa_key_pair)
    _write_key_pair(tmp_path, "ec-key-1", ec_key_pair)
    repository = LocalFileKeyRepository(
        keys_directory=tmp_path, trusted_key_ids_override=frozenset({"rsa-key-1"})
    )

    assert repository.trusted_key_ids() == {"rsa-key-1"}
