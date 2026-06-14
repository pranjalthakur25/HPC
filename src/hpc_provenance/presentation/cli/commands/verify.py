"""``hpc-provenance verify`` command group."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from hpc_provenance.config.container import Container
from hpc_provenance.config.settings import Settings
from hpc_provenance.domain.exceptions import VerificationError
from hpc_provenance.domain.models.dsse import DSSEEnvelope
from hpc_provenance.domain.models.verification import VerificationPolicy
from hpc_provenance.domain.value_objects import VerificationKey

app = typer.Typer(no_args_is_help=True)


@app.command("run")
def run(
    record_id: str = typer.Argument(..., help="Provenance record id, as returned by `sign run`."),
    trusted_key_id: list[str] = typer.Option(
        [],
        "--trusted-key-id",
        help="Trusted verification key id(s) (repeatable; default: all known keys).",
    ),
    expected_builder_id: str | None = typer.Option(
        None, "--expected-builder-id", help="Fail verification if the statement's builder id differs."
    ),
    expected_source_repo: str | None = typer.Option(
        None,
        "--expected-source-repo",
        help="Fail verification if the statement's source repo URI differs.",
    ),
) -> None:
    """Load a stored DSSE envelope and verify it against a
    ``VerificationPolicy`` assembled from the given options.

    Wires a ``VerifyProvenanceRequest`` and calls
    ``Container.verify_provenance_use_case().execute(...)``. Exits non-zero
    if ``VerificationResult.is_valid`` is ``False``.
    """
    raise NotImplementedError


@app.command("attestation")
def attestation(
    path: Path = typer.Argument(
        ..., exists=True, help="Path to a DSSE attestation file (e.g. attestation.dsse)."
    ),
    trusted_key_id: list[str] = typer.Option(
        [],
        "--trusted-key-id",
        help="Trusted verification key id(s) (repeatable; default: all known keys).",
    ),
    expected_builder_id: str | None = typer.Option(
        None, "--expected-builder-id", help="Fail verification if the statement's builder id differs."
    ),
    expected_source_repo: str | None = typer.Option(
        None,
        "--expected-source-repo",
        help="Fail verification if the statement's source repo URI differs.",
    ),
    required_predicate_type: str | None = typer.Option(
        None,
        "--required-predicate-type",
        help="Fail verification if the statement's predicate type differs.",
    ),
) -> None:
    """Verify a standalone DSSE attestation file (e.g. produced by
    ``slurm epilogue`` or ``sign run -o``) against a ``VerificationPolicy``.

    Unlike ``verify run``, this reads the envelope directly from ``path``
    rather than from the provenance catalog, so it works without the
    record id assigned by ``sign run``.
    """
    container = Container(Settings())
    envelope = DSSEEnvelope.from_dict(json.loads(path.read_text()))

    trusted_key_ids = (
        frozenset(trusted_key_id) if trusted_key_id else container.key_repository.trusted_key_ids()
    )

    verification_keys: dict[str, VerificationKey] = {}
    for signature in envelope.signatures:
        if signature.key_id is None or signature.key_id in verification_keys:
            continue
        try:
            verification_keys[signature.key_id] = container.key_repository.get_verification_key(
                signature.key_id
            )
        except VerificationError:
            continue

    policy = VerificationPolicy(
        trusted_key_ids=trusted_key_ids,
        expected_builder_id=expected_builder_id,
        expected_source_repo_uri=expected_source_repo,
        required_predicate_type=required_predicate_type,
    )

    result = container.envelope_verifier.verify(envelope, policy, verification_keys)

    for issue in result.issues:
        typer.echo(f"{issue.severity.value.upper()}: {issue.code}: {issue.message}", err=True)

    if not result.is_valid:
        typer.echo("INVALID", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"VALID (verified keys: {', '.join(result.verified_key_ids)})")
