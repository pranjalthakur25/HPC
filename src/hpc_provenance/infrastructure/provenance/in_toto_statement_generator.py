"""``InTotoStatementGenerator`` -- the entry point for in-toto Statement generation.

Takes a SLSA provenance predicate plus the subjects it describes and wraps
them in an in-toto v1 ``Statement`` (``_type``, ``subject``,
``predicateType``, ``predicate``), plus helpers to serialize that statement
to JSON and write it out as ``statement.json``.

Deliberately does **not** wrap the statement in a DSSE envelope -- that
remains the responsibility of the signing infrastructure, which this module
does not import.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from hpc_provenance.domain.interfaces.provenance import InTotoStatementBuilder
from hpc_provenance.domain.models.in_toto import InTotoStatement
from hpc_provenance.domain.models.provenance import ResourceDescriptor, SLSAProvenancePredicate
from hpc_provenance.infrastructure.provenance.in_toto_statement_builder import InTotoV1StatementBuilder


class InTotoStatementGenerator:
    """Generates in-toto v1 Statements wrapping a SLSA provenance predicate.

    Wraps an ``InTotoStatementBuilder`` (defaults to
    ``InTotoV1StatementBuilder``) so the statement-construction strategy
    stays swappable -- e.g. a future in-toto version, or a builder for a
    different predicate type, can be injected without changing callers.
    """

    def __init__(self, statement_builder: InTotoStatementBuilder | None = None) -> None:
        self._statement_builder = statement_builder or InTotoV1StatementBuilder()

    def generate(
        self,
        subjects: Sequence[ResourceDescriptor],
        predicate_type: str,
        predicate: SLSAProvenancePredicate,
    ) -> InTotoStatement:
        """Build an ``InTotoStatement`` wrapping ``predicate`` and describing
        ``subjects``.

        Raises:
            ProvenanceGenerationError: propagated from the underlying
                ``InTotoStatementBuilder``.
        """
        return self._statement_builder.build(subjects, predicate_type, predicate)

    def to_dict(self, statement: InTotoStatement) -> dict[str, object]:
        """Serialize ``statement`` to the in-toto Statement v1 JSON shape
        (``_type``, ``subject``, ``predicateType``, ``predicate``).
        """
        return statement.to_dict()

    def to_json(self, statement: InTotoStatement, *, indent: int | None = 2) -> str:
        """Serialize ``statement`` as a JSON string."""
        return statement.to_json(indent=indent)

    def write_statement(self, statement: InTotoStatement, output_path: Path) -> Path:
        """Write ``statement`` as JSON to ``output_path`` (conventionally
        ``statement.json``) and return that path.
        """
        output_path.write_text(self.to_json(statement), encoding="utf-8")
        return output_path

    def generate_statement_file(
        self,
        subjects: Sequence[ResourceDescriptor],
        predicate_type: str,
        predicate: SLSAProvenancePredicate,
        output_path: Path,
    ) -> Path:
        """Generate a statement from ``predicate``/``subjects`` and write it
        to ``output_path`` in one step. Returns ``output_path``.
        """
        statement = self.generate(subjects, predicate_type, predicate)
        return self.write_statement(statement, output_path)
