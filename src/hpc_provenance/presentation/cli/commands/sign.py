"""``hpc-provenance sign`` command group."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from hpc_provenance.application.dto.requests import SignProvenanceRequest
from hpc_provenance.config.container import Container
from hpc_provenance.config.settings import Settings
from hpc_provenance.domain.models.in_toto import InTotoStatement

app = typer.Typer(no_args_is_help=True)


@app.command("run")
def run(
    statement: Path = typer.Argument(
        ...,
        exists=True,
        help="Path to an in-toto Statement JSON file (e.g. from `generate run -o`).",
    ),
    key_id: list[str] = typer.Option(
        ..., "--key-id", help="Signing key id(s) to use (repeatable)."
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Write the DSSE envelope JSON here (default: stdout)."
    ),
) -> None:
    """Sign an in-toto Statement into a DSSE envelope and persist it via the
    configured ``ProvenanceRepository``.

    Wires a ``SignProvenanceRequest`` and calls
    ``Container.sign_provenance_use_case().execute(...)``.
    """
    in_toto_statement = InTotoStatement.from_dict(json.loads(statement.read_text()))

    request = SignProvenanceRequest(
        statement=in_toto_statement,
        signing_key_ids=tuple(key_id),
    )

    result = Container(Settings()).sign_provenance_use_case().execute(request)

    envelope_json = json.dumps(result.envelope.to_dict(), indent=2)
    if output is not None:
        output.write_text(envelope_json)
    else:
        typer.echo(envelope_json)

    typer.echo(f"record id: {result.record_id.value}", err=True)
