"""Top-level CLI application: registers command groups."""

from __future__ import annotations

import typer

from hpc_provenance.presentation.cli.commands import generate, keys, sign, slurm, verify

app = typer.Typer(
    name="hpc-provenance",
    help="Generate, sign, and verify SLSA-style provenance for HPC (Slurm) jobs.",
    no_args_is_help=True,
)
app.add_typer(generate.app, name="generate", help="Generate an in-toto/SLSA provenance statement.")
app.add_typer(sign.app, name="sign", help="Sign a provenance statement into a DSSE envelope.")
app.add_typer(verify.app, name="verify", help="Verify a signed provenance envelope.")
app.add_typer(keys.app, name="keys", help="Manage signing/verification key pairs.")
app.add_typer(slurm.app, name="slurm", help="Slurm sbatch prologue/epilogue hooks.")


def main() -> None:
    """Entry point registered as the ``hpc-provenance`` console script."""
    app()
