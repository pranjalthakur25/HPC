"""Generic, validated domain models for provenance generation.

These models capture build/artifact/builder/invocation metadata in a form
that is independent of any specific attestation format (SLSA, in-toto, ...).
A later step -- not implemented here -- is responsible for mapping these
objects onto SLSA predicate structures (see ``domain.models.provenance``).

Unlike most other domain models in this package, these validate their fields
on construction (raising ``InvalidMetadataError``) and provide ``to_dict()``/
``to_json()`` for direct serialization.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from hpc_provenance.domain.exceptions import InvalidMetadataError
from hpc_provenance.domain.value_objects import Digest, ResourceURI


class _SerializableMixin:
    """Provides ``to_json()`` for dataclasses that implement ``to_dict()``."""

    __slots__ = ()

    def to_dict(self) -> Mapping[str, object]:
        raise NotImplementedError

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialize ``to_dict()`` as a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise InvalidMetadataError(f"{field_name} must not be empty")


def _validate_digests(digests: tuple[Digest, ...], owner: str) -> None:
    if not digests:
        raise InvalidMetadataError(f"{owner}.digests must contain at least one digest")
    algorithms = [digest.algorithm for digest in digests]
    if len(algorithms) != len(set(algorithms)):
        raise InvalidMetadataError(f"{owner}.digests must not repeat a digest algorithm")


def _digest_set(digests: tuple[Digest, ...]) -> dict[str, str]:
    digest_set: dict[str, str] = {}
    for digest in digests:
        digest_set.update(digest.as_digest_set())
    return digest_set


@dataclass(frozen=True, slots=True)
class Subject(_SerializableMixin):
    """An in-toto Statement subject: an artifact identified by name + digest."""

    name: str
    digests: tuple[Digest, ...]

    def __post_init__(self) -> None:
        _require_non_empty(self.name, "Subject.name")
        _validate_digests(self.digests, "Subject")

    def to_dict(self) -> dict[str, object]:
        return {"name": self.name, "digest": _digest_set(self.digests)}


@dataclass(frozen=True, slots=True)
class ArtifactMetadata(_SerializableMixin):
    """Metadata describing a single build input or output artifact."""

    name: str
    digests: tuple[Digest, ...]
    uri: ResourceURI | None = None
    media_type: str | None = None
    size_bytes: int | None = None
    local_path: Path | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.name, "ArtifactMetadata.name")
        _validate_digests(self.digests, "ArtifactMetadata")
        if self.uri is not None:
            _require_non_empty(self.uri, "ArtifactMetadata.uri")
        if self.media_type is not None:
            _require_non_empty(self.media_type, "ArtifactMetadata.media_type")
        if self.size_bytes is not None and self.size_bytes < 0:
            raise InvalidMetadataError("ArtifactMetadata.size_bytes must not be negative")

    def as_subject(self) -> Subject:
        """Return the in-toto ``Subject`` view of this artifact."""
        return Subject(name=self.name, digests=self.digests)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "digest": _digest_set(self.digests),
            "uri": self.uri,
            "mediaType": self.media_type,
            "sizeBytes": self.size_bytes,
            "localPath": str(self.local_path) if self.local_path is not None else None,
        }


@dataclass(frozen=True, slots=True)
class BuilderMetadata(_SerializableMixin):
    """Identifies the entity (service, host, pipeline) that performed a build."""

    id: ResourceURI
    name: str | None = None
    version: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.id, "BuilderMetadata.id")
        if self.name is not None:
            _require_non_empty(self.name, "BuilderMetadata.name")
        if self.version is not None:
            _require_non_empty(self.version, "BuilderMetadata.version")

    def to_dict(self) -> dict[str, object]:
        return {"id": self.id, "name": self.name, "version": self.version}


@dataclass(frozen=True, slots=True)
class InvocationMetadata(_SerializableMixin):
    """Describes how and when a build was invoked."""

    invocation_id: str
    command: tuple[str, ...]
    working_directory: Path
    environment: Mapping[str, str] = field(default_factory=dict)
    parameters: Mapping[str, object] = field(default_factory=dict)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.invocation_id, "InvocationMetadata.invocation_id")
        if not self.command:
            raise InvalidMetadataError("InvocationMetadata.command must not be empty")
        if (
            self.started_at is not None
            and self.finished_at is not None
            and self.finished_at < self.started_at
        ):
            raise InvalidMetadataError(
                "InvocationMetadata.finished_at must not be before started_at"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "invocationId": self.invocation_id,
            "command": list(self.command),
            "workingDirectory": str(self.working_directory),
            "environment": dict(self.environment),
            "parameters": dict(self.parameters),
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "finishedAt": self.finished_at.isoformat() if self.finished_at else None,
        }


@dataclass(frozen=True, slots=True)
class BuildMetadata(_SerializableMixin):
    """Timing and identification metadata for a single build invocation.

    Used as ``RunDetails.metadata`` in ``domain.models.provenance``.
    """

    invocation_id: str | None
    started_on: datetime | None
    finished_on: datetime | None

    def __post_init__(self) -> None:
        if self.invocation_id is not None:
            _require_non_empty(self.invocation_id, "BuildMetadata.invocation_id")
        if (
            self.started_on is not None
            and self.finished_on is not None
            and self.finished_on < self.started_on
        ):
            raise InvalidMetadataError("BuildMetadata.finished_on must not be before started_on")

    def to_dict(self) -> dict[str, object]:
        return {
            "invocationId": self.invocation_id,
            "startedOn": self.started_on.isoformat() if self.started_on else None,
            "finishedOn": self.finished_on.isoformat() if self.finished_on else None,
        }
