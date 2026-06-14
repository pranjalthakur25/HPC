"""Application configuration, loaded from environment variables / a `.env` file."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from hpc_provenance.domain.enums import DigestAlgorithm, SchedulerType


class Settings(BaseSettings):
    """Runtime configuration for ``hpc-provenance``.

    Every field can be overridden by an environment variable prefixed with
    ``HPC_PROVENANCE_`` (e.g. ``HPC_PROVENANCE_BUILDER_ID``) or via a
    ``.env`` file in the working directory. This is the only place
    environment/config files are read.
    """

    model_config = SettingsConfigDict(
        env_prefix="HPC_PROVENANCE_", env_file=".env", extra="forbid"
    )

    scheduler_type: SchedulerType = SchedulerType.SLURM
    """Selects which `SchedulerMetadataCollector` the container constructs."""

    builder_id: str = "https://example.org/hpc-provenance/builder/v1"
    """Default `BuilderIdentity.id` used by `SLSAv1PredicateBuilder`."""

    digest_algorithm: DigestAlgorithm = DigestAlgorithm.SHA256
    """Hash algorithm used by `FilesystemArtifactCollector`."""

    output_directory: Path = Path("./provenance")
    """Root directory for `FilesystemProvenanceRepository`."""

    keys_directory: Path = Path("./keys")
    """Root directory for `LocalFileKeyRepository`."""

    trusted_key_ids: frozenset[str] | None = None
    """Optional override restricting `LocalFileKeyRepository.trusted_key_ids()`."""
