"""Domain models for the Observer Agent: declared build inputs/outputs for a
job (``JobManifest``) and the outcome of processing one completed job
(``ObservedJob``/``ObserverPollResult``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from hpc_provenance.domain.enums import ObservedJobStatus
from hpc_provenance.domain.models.verification import VerificationResult
from hpc_provenance.domain.value_objects import JobIdentifier


@dataclass(frozen=True, slots=True)
class JobManifest:
    """A job's declared build definition, read from ``provenance.manifest.json``
    in its working directory.

    All paths are resolved (absolute) by the repository that loads this
    manifest -- relative paths in the JSON file are resolved against the
    job's working directory.
    """

    product_paths: tuple[Path, ...]
    material_paths: tuple[Path, ...] = ()
    signing_key_ids: tuple[str, ...] = ()
    git_repository_path: Path | None = None
    output_dir: Path | None = None


@dataclass(frozen=True, slots=True)
class ObservedJob:
    """The outcome of the Observer Agent processing a single completed job."""

    job_id: JobIdentifier
    status: ObservedJobStatus
    statement_path: Path | None = None
    envelope_path: Path | None = None
    verification: VerificationResult | None = None
    message: str | None = None


@dataclass(frozen=True, slots=True)
class ObserverPollResult:
    """The outcome of a single ``ObserverService.poll_once`` call."""

    observed: tuple[ObservedJob, ...]
    polled_at: datetime
