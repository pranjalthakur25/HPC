"""``SlsaPredicateGenerator`` -- the entry point for SLSA v1 predicate generation.

Takes the collected metadata models (bundled as a ``ProvenanceContext``) and
produces a ``SLSAProvenancePredicate``, plus helpers to serialize that
predicate to JSON and write it out as ``predicate.json``.

Deliberately does **not** wrap the predicate in an in-toto ``Statement`` or a
DSSE envelope -- that remains the responsibility of
``InTotoStatementBuilder``/the signing infrastructure, which this module does
not import.
"""

from __future__ import annotations

import json
from pathlib import Path

from hpc_provenance.domain.interfaces.provenance import ProvenancePredicateBuilder
from hpc_provenance.domain.models.provenance import SLSAProvenancePredicate
from hpc_provenance.domain.models.provenance_context import ProvenanceContext
from hpc_provenance.infrastructure.provenance.slsa_predicate_builder import SLSAv1PredicateBuilder
from hpc_provenance.infrastructure.provenance.slsa_predicate_mapper import predicate_to_dict


class SlsaPredicateGenerator:
    """Generates SLSA v1 provenance predicates from collected metadata.

    Wraps a ``ProvenancePredicateBuilder`` (defaults to
    ``SLSAv1PredicateBuilder``) so the predicate-construction strategy stays
    swappable -- e.g. a future SLSA v1.1 predicate builder, or a builder
    specialized for a different HPC scheduler, can be injected without
    changing callers.
    """

    def __init__(self, predicate_builder: ProvenancePredicateBuilder | None = None) -> None:
        self._predicate_builder = predicate_builder or SLSAv1PredicateBuilder()

    @property
    def predicate_type(self) -> str:
        """The in-toto ``predicateType`` URI of generated predicates."""
        return self._predicate_builder.predicate_type

    def generate(self, context: ProvenanceContext) -> SLSAProvenancePredicate:
        """Build a ``SLSAProvenancePredicate`` from collected metadata.

        Raises:
            ProvenanceGenerationError: propagated from the underlying
                ``ProvenancePredicateBuilder``.
        """
        return self._predicate_builder.build(context)

    def to_dict(self, predicate: SLSAProvenancePredicate) -> dict[str, object]:
        """Serialize ``predicate`` to the SLSA v1 ``predicate`` JSON shape."""
        return predicate_to_dict(predicate)

    def to_json(self, predicate: SLSAProvenancePredicate, *, indent: int | None = 2) -> str:
        """Serialize ``predicate`` as a JSON string."""
        return json.dumps(self.to_dict(predicate), indent=indent)

    def write_predicate(self, predicate: SLSAProvenancePredicate, output_path: Path) -> Path:
        """Write ``predicate`` as JSON to ``output_path`` (conventionally
        ``predicate.json``) and return that path.
        """
        output_path.write_text(self.to_json(predicate), encoding="utf-8")
        return output_path

    def generate_predicate_file(self, context: ProvenanceContext, output_path: Path) -> Path:
        """Generate a predicate from ``context`` and write it to
        ``output_path`` in one step. Returns ``output_path``.
        """
        predicate = self.generate(context)
        return self.write_predicate(predicate, output_path)
