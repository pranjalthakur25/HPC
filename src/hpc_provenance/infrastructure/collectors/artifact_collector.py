"""Filesystem-backed implementation of ``ArtifactMetadataCollector``."""

from __future__ import annotations

import hashlib
import mimetypes
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from hpc_provenance.domain.enums import ArtifactRole, DigestAlgorithm
from hpc_provenance.domain.exceptions import MetadataCollectionError
from hpc_provenance.domain.interfaces.collectors import ArtifactMetadataCollector
from hpc_provenance.domain.models.artifact import Artifact
from hpc_provenance.domain.value_objects import Digest

_CHUNK_SIZE = 1024 * 1024  # 1 MiB


class FilesystemArtifactCollector(ArtifactMetadataCollector):
    """Computes digests and basic metadata for files on a local (or shared
    HPC) filesystem.
    """

    def __init__(self, digest_algorithm: DigestAlgorithm = DigestAlgorithm.SHA256) -> None:
        """``digest_algorithm`` selects the hash used for each ``Artifact.digest``."""
        self._digest_algorithm = digest_algorithm

    def collect(self, paths: Iterable[Path], role: ArtifactRole) -> tuple[Artifact, ...]:
        """See ``ArtifactMetadataCollector.collect``."""
        return tuple(self._collect_one(Path(path), role) for path in paths)

    def _collect_one(self, path: Path, role: ArtifactRole) -> Artifact:
        if not path.exists():
            raise MetadataCollectionError(f"artifact path does not exist: {path}")
        if not path.is_file():
            raise MetadataCollectionError(f"artifact path is not a file: {path}")

        resolved = path.resolve()
        try:
            stat_result = resolved.stat()
            hex_digest = self._hash_file(resolved)
        except OSError as exc:
            raise MetadataCollectionError(f"failed to read artifact {path}: {exc}") from exc

        media_type, _ = mimetypes.guess_type(resolved.name)

        return Artifact(
            name=resolved.name,
            uri=resolved.as_uri(),
            digest=Digest(algorithm=self._digest_algorithm, hex_value=hex_digest),
            media_type=media_type,
            size_bytes=stat_result.st_size,
            role=role,
            created_at=datetime.fromtimestamp(stat_result.st_mtime, tz=timezone.utc),
        )

    def _hash_file(self, path: Path) -> str:
        digest = hashlib.new(self._digest_algorithm.value)
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(_CHUNK_SIZE), b""):
                digest.update(chunk)
        return digest.hexdigest()
