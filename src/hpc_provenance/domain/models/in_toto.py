"""in-toto Statement domain model (https://github.com/in-toto/attestation)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass

from hpc_provenance.domain.models.provenance import ResourceDescriptor

IN_TOTO_STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
"""The fixed in-toto Statement ``_type`` value for v1 statements."""


@dataclass(frozen=True, slots=True)
class InTotoStatement:
    """An in-toto v1 Statement: a typed wrapper around a predicate.

    ``predicate`` is kept as ``Mapping[str, object]`` (the serialized form
    of, e.g., a ``SLSAProvenancePredicate``) so this model stays agnostic of
    which predicate type it carries.
    """

    subjects: tuple[ResourceDescriptor, ...]
    predicate_type: str
    predicate: Mapping[str, object]
    type_: str = IN_TOTO_STATEMENT_TYPE

    def to_dict(self) -> dict[str, object]:
        """Map this statement to its in-toto Statement v1 JSON shape:
        ``{"_type", "subject", "predicateType", "predicate"}``.

        See https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md.
        """
        return {
            "_type": self.type_,
            "subject": [subject.to_dict() for subject in self.subjects],
            "predicateType": self.predicate_type,
            "predicate": dict(self.predicate),
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialize ``to_dict()`` as a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> InTotoStatement:
        """Build an ``InTotoStatement`` from its in-toto Statement v1 JSON shape.

        Inverse of ``to_dict()``.
        """
        subjects = data.get("subject", [])
        if not isinstance(subjects, list):
            subjects = []
        predicate = data["predicate"]
        return cls(
            subjects=tuple(ResourceDescriptor.from_dict(subject) for subject in subjects),
            predicate_type=str(data["predicateType"]),
            predicate=dict(predicate) if isinstance(predicate, Mapping) else {},
            type_=str(data.get("_type", IN_TOTO_STATEMENT_TYPE)),
        )

    @classmethod
    def from_json(cls, text: str) -> InTotoStatement:
        """Build an ``InTotoStatement`` from its in-toto Statement v1 JSON string."""
        return cls.from_dict(json.loads(text))
