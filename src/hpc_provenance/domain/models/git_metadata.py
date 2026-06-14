"""Domain models describing the git repository state at job execution time."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class GitCommit:
    """A single git commit."""

    sha: str
    author_name: str
    author_email: str
    committed_at: datetime
    message: str


@dataclass(frozen=True, slots=True)
class GitRepositoryMetadata:
    """The state of a git repository at the time a job was executed.

    Captured as a SLSA "material" describing the source that produced the
    job's artifacts.
    """

    remote_url: str | None
    branch: str | None
    tags: tuple[str, ...]
    is_dirty: bool
    root_path: Path
    commit: GitCommit
