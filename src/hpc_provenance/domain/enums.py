"""Enumerations shared across the domain layer."""

from __future__ import annotations

from enum import Enum


class DigestAlgorithm(str, Enum):
    """Cryptographic digest algorithms used to identify artifacts."""

    SHA256 = "sha256"
    SHA512 = "sha512"
    SHA1 = "sha1"


class SchedulerType(str, Enum):
    """HPC job schedulers supported (or planned) as metadata sources."""

    SLURM = "slurm"


class JobState(str, Enum):
    """Terminal and non-terminal states of an HPC job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    OUT_OF_MEMORY = "out_of_memory"
    UNKNOWN = "unknown"


class ArtifactRole(str, Enum):
    """The role an artifact plays in a build, per SLSA terminology."""

    MATERIAL = "material"
    PRODUCT = "product"
    BYPRODUCT = "byproduct"


class IssueSeverity(str, Enum):
    """Severity of a single verification finding."""

    ERROR = "error"
    WARNING = "warning"


class ObservedJobStatus(str, Enum):
    """Outcome of the Observer Agent processing a single completed job."""

    PROCESSED = "processed"
    SKIPPED_NO_MANIFEST = "skipped_no_manifest"
    ERROR = "error"
