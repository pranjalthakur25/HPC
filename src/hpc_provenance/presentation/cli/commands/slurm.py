"""``hpc-provenance slurm`` command group: prologue/epilogue hooks for
``sbatch`` scripts (see ``examples/train.sh``).

Both commands read ``SLURM_*`` environment variables directly and run as the
submitting user -- no scheduler-admin privileges or ``slurm.conf`` changes
are required.
"""

from __future__ import annotations

from pathlib import Path

import typer

from hpc_provenance.config.container import Container
from hpc_provenance.config.settings import Settings

app = typer.Typer(no_args_is_help=True)


@app.command("prologue")
def prologue(
    git_repo: Path | None = typer.Option(
        None,
        "--git-repo",
        exists=True,
        file_okay=False,
        help="Path to the git repository to record in the prologue snapshot.",
    ),
    output_dir: Path | None = typer.Option(
        None,
        "--output-dir",
        help="Directory to write prologue.json (default: $SLURM_SUBMIT_DIR).",
    ),
) -> None:
    """Write a job-start snapshot (job id/user/nodelist/partition + git
    state) to ``<output-dir>/prologue.json``.

    Call this near the start of an ``sbatch`` script. Informational only:
    ``slurm epilogue`` re-collects all metadata independently.
    """
    path = (
        Container(Settings())
        .slurm_provenance_service()
        .run_prologue(git_repository_path=git_repo, output_dir=output_dir)
    )
    typer.echo(f"wrote {path}")


@app.command("epilogue")
def epilogue(
    products: list[Path] = typer.Option(
        ..., "--product", exists=True, help="Output artifact path(s) (repeatable, required)."
    ),
    materials: list[Path] = typer.Option(
        [], "--material", exists=True, help="Input artifact path(s) (repeatable)."
    ),
    git_repo: Path | None = typer.Option(
        None,
        "--git-repo",
        exists=True,
        file_okay=False,
        help="Path to the git repository to record as a material.",
    ),
    key_id: list[str] = typer.Option(
        ..., "--key-id", help="Signing key id(s) to use (repeatable)."
    ),
    builder_id: str | None = typer.Option(
        None,
        "--builder-id",
        help="URI identifying this builder (default: the configured builder id).",
    ),
    output_dir: Path | None = typer.Option(
        None,
        "--output-dir",
        help="Directory to write provenance.json/attestation.dsse (default: $SLURM_SUBMIT_DIR).",
    ),
) -> None:
    """Generate and sign provenance for the just-completed job, writing
    ``provenance.json`` and ``attestation.dsse`` to ``<output-dir>``.

    Call this near the end of an ``sbatch`` script, after the workload has
    produced its output artifacts.
    """
    settings = Settings()
    result = (
        Container(settings)
        .slurm_provenance_service()
        .run_epilogue(
            builder_id=builder_id or settings.builder_id,
            signing_key_ids=tuple(key_id),
            product_paths=tuple(products),
            material_paths=tuple(materials),
            git_repository_path=git_repo,
            output_dir=output_dir,
        )
    )
    typer.echo(f"wrote {result.statement_path}")
    typer.echo(f"wrote {result.envelope_path}")
    typer.echo(f"record id: {result.record_id.value}", err=True)
