"""``hpc-provenance generate`` command group."""

from __future__ import annotations

from pathlib import Path

import typer

from hpc_provenance.application.dto.requests import GenerateProvenanceRequest
from hpc_provenance.config.container import Container
from hpc_provenance.config.settings import Settings
from hpc_provenance.domain.enums import SchedulerType
from hpc_provenance.domain.value_objects import JobIdentifier

app = typer.Typer(no_args_is_help=True)


@app.command("run")
def run(
    job_id: str | None = typer.Option(
        None, "--job-id", help="Slurm job id (defaults to $SLURM_JOB_ID)."
    ),
    git_repo: Path | None = typer.Option(
        None,
        "--git-repo",
        exists=True,
        file_okay=False,
        help="Path to the git repository to record as a material.",
    ),
    materials: list[Path] = typer.Option(
        [], "--material", exists=True, help="Input artifact path(s) (repeatable)."
    ),
    products: list[Path] = typer.Option(
        ..., "--product", exists=True, help="Output artifact path(s) (repeatable, required)."
    ),
    builder_id: str = typer.Option(
        ...,
        "--builder-id",
        help="URI identifying this builder, e.g. https://example.org/hpc-provenance/builder/v1.",
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Write the in-toto statement JSON here (default: stdout)."
    ),
) -> None:
    """Collect git/Slurm/artifact metadata and emit an in-toto Statement
    carrying a SLSA provenance predicate.

    Wires a ``GenerateProvenanceRequest`` and calls
    ``Container.generate_provenance_use_case().execute(...)``.
    """
    request = GenerateProvenanceRequest(
        builder_id=builder_id,
        product_paths=tuple(products),
        material_paths=tuple(materials),
        job_id=JobIdentifier(scheduler=SchedulerType.SLURM, value=job_id)
        if job_id is not None
        else None,
        git_repository_path=git_repo,
    )

    statement = Container(Settings()).generate_provenance_use_case().execute(request)

    if output is not None:
        output.write_text(statement.to_json())
    else:
        typer.echo(statement.to_json())
