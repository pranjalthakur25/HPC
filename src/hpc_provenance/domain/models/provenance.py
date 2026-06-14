"""SLSA Provenance v1 predicate domain models.

Mirrors the structure of https://slsa.dev/spec/v1.0/provenance as plain
dataclasses, so the domain layer has no dependency on a JSON schema library;
serialization is an infrastructure concern.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from hpc_provenance.domain.models.provenance_metadata import BuildMetadata


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None


@dataclass(frozen=True, slots=True)
class ResourceDescriptor:
    """An in-toto ResourceDescriptor: identifies a resource by URI/digest."""

    name: str | None = None
    uri: str | None = None
    digest: Mapping[str, str] = field(default_factory=dict)
    content: bytes | None = None
    download_location: str | None = None
    media_type: str | None = None
    annotations: Mapping[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        """Map this descriptor to its in-toto ResourceDescriptor JSON shape.

        Fields that are unset (``None`` or empty) are omitted, matching the
        in-toto/SLSA examples (which do not emit ``null`` for absent optional
        fields).
        """
        result: dict[str, object] = {}
        if self.name is not None:
            result["name"] = self.name
        if self.uri is not None:
            result["uri"] = self.uri
        if self.digest:
            result["digest"] = dict(self.digest)
        if self.download_location is not None:
            result["downloadLocation"] = self.download_location
        if self.media_type is not None:
            result["mediaType"] = self.media_type
        if self.annotations:
            result["annotations"] = dict(self.annotations)
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> ResourceDescriptor:
        """Build a ``ResourceDescriptor`` from its in-toto JSON shape.

        Inverse of ``to_dict()``; fields absent from ``data`` map to their
        ``None``/empty defaults.
        """
        digest = data.get("digest", {})
        annotations = data.get("annotations")
        return cls(
            name=_optional_str(data.get("name")),
            uri=_optional_str(data.get("uri")),
            digest=digest if isinstance(digest, Mapping) else {},
            download_location=_optional_str(data.get("downloadLocation")),
            media_type=_optional_str(data.get("mediaType")),
            annotations=annotations if isinstance(annotations, Mapping) else None,
        )


@dataclass(frozen=True, slots=True)
class BuilderIdentity:
    """Identifies the entity that performed the build."""

    id: str
    version: Mapping[str, str] | None = None
    builder_dependencies: tuple[ResourceDescriptor, ...] = ()


@dataclass(frozen=True, slots=True)
class BuildDefinition:
    """Describes *what* was built and *how*, independent of *who* built it."""

    build_type: str
    external_parameters: Mapping[str, object]
    internal_parameters: Mapping[str, object]
    resolved_dependencies: tuple[ResourceDescriptor, ...] = ()


@dataclass(frozen=True, slots=True)
class RunDetails:
    """Describes *who* performed the build and runtime details."""

    builder: BuilderIdentity
    metadata: BuildMetadata
    byproducts: tuple[ResourceDescriptor, ...] = ()


@dataclass(frozen=True, slots=True)
class SLSAProvenancePredicate:
    """The full SLSA v1 ``predicate`` object: ``{buildDefinition, runDetails}``."""

    build_definition: BuildDefinition
    run_details: RunDetails
