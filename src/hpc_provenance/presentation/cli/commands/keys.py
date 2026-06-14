"""``hpc-provenance keys`` command group."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

import typer
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.asymmetric.types import PrivateKeyTypes

app = typer.Typer(no_args_is_help=True)


class KeyAlgorithm(str, Enum):
    """Supported key-pair algorithms for ``keys generate``."""

    RSA = "rsa"
    ECDSA = "ecdsa"


def _generate_private_key(algorithm: KeyAlgorithm) -> PrivateKeyTypes:
    match algorithm:
        case KeyAlgorithm.RSA:
            return rsa.generate_private_key(public_exponent=65537, key_size=2048)
        case KeyAlgorithm.ECDSA:
            return ec.generate_private_key(ec.SECP256R1())


@app.command("generate")
def generate(
    key_id: str = typer.Argument(..., help="Identifier for the generated key pair."),
    algorithm: KeyAlgorithm = typer.Option(
        KeyAlgorithm.ECDSA, "--algorithm", help="Key pair algorithm."
    ),
    keys_dir: Path = typer.Option(
        Path("./keys"), "--keys-dir", help="Directory to write the key pair into."
    ),
) -> None:
    """Generate an RSA or ECDSA key pair for signing and verifying provenance.

    Writes ``<keys-dir>/<key-id>.private.pem`` (PKCS8, unencrypted) and
    ``<keys-dir>/<key-id>.public.pem`` (SubjectPublicKeyInfo), the layout
    expected by ``LocalFileKeyRepository``.
    """
    keys_dir.mkdir(parents=True, exist_ok=True)

    private_key = _generate_private_key(algorithm)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    private_path = keys_dir / f"{key_id}.private.pem"
    public_path = keys_dir / f"{key_id}.public.pem"
    private_path.write_bytes(private_pem)
    public_path.write_bytes(public_pem)

    typer.echo(f"Wrote {private_path}")
    typer.echo(f"Wrote {public_path}")
