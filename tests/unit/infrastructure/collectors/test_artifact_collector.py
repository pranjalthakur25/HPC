"""Unit tests for ``FilesystemArtifactCollector``."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from hpc_provenance.domain.enums import ArtifactRole, DigestAlgorithm
from hpc_provenance.domain.exceptions import MetadataCollectionError
from hpc_provenance.infrastructure.collectors.artifact_collector import FilesystemArtifactCollector


def test_collect_computes_digest_and_metadata(tmp_path: Path) -> None:
    content = b"hello world\n"
    file_path = tmp_path / "model.txt"
    file_path.write_bytes(content)

    collector = FilesystemArtifactCollector()
    (artifact,) = collector.collect([file_path], ArtifactRole.PRODUCT)

    assert artifact.name == "model.txt"
    assert artifact.uri == file_path.resolve().as_uri()
    assert artifact.digest.algorithm == DigestAlgorithm.SHA256
    assert artifact.digest.hex_value == hashlib.sha256(content).hexdigest()
    assert artifact.size_bytes == len(content)
    assert artifact.role == ArtifactRole.PRODUCT
    assert artifact.created_at is not None
    assert artifact.created_at.tzinfo is not None


def test_collect_uses_configured_digest_algorithm(tmp_path: Path) -> None:
    file_path = tmp_path / "data.bin"
    file_path.write_bytes(b"payload")

    collector = FilesystemArtifactCollector(digest_algorithm=DigestAlgorithm.SHA512)
    (artifact,) = collector.collect([file_path], ArtifactRole.MATERIAL)

    assert artifact.digest.algorithm == DigestAlgorithm.SHA512
    assert artifact.digest.hex_value == hashlib.sha512(b"payload").hexdigest()


def test_collect_guesses_media_type(tmp_path: Path) -> None:
    file_path = tmp_path / "report.json"
    file_path.write_text("{}")

    collector = FilesystemArtifactCollector()
    (artifact,) = collector.collect([file_path], ArtifactRole.PRODUCT)

    assert artifact.media_type == "application/json"


def test_collect_handles_multiple_paths(tmp_path: Path) -> None:
    paths = []
    for i in range(2):
        path = tmp_path / f"file{i}.txt"
        path.write_text(f"content {i}")
        paths.append(path)

    collector = FilesystemArtifactCollector()
    artifacts = collector.collect(paths, ArtifactRole.MATERIAL)

    assert len(artifacts) == 2
    assert {artifact.name for artifact in artifacts} == {"file0.txt", "file1.txt"}
    assert all(artifact.role == ArtifactRole.MATERIAL for artifact in artifacts)


def test_collect_raises_for_missing_path(tmp_path: Path) -> None:
    collector = FilesystemArtifactCollector()

    with pytest.raises(MetadataCollectionError):
        collector.collect([tmp_path / "missing.txt"], ArtifactRole.PRODUCT)


def test_collect_raises_for_directory(tmp_path: Path) -> None:
    collector = FilesystemArtifactCollector()

    with pytest.raises(MetadataCollectionError):
        collector.collect([tmp_path], ArtifactRole.PRODUCT)
