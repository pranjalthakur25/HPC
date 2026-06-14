"""Local-filesystem implementation of ``KeyRepository``."""

from __future__ import annotations

from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from hpc_provenance.domain.exceptions import SigningError, VerificationError
from hpc_provenance.domain.interfaces.repositories import KeyRepository
from hpc_provenance.domain.value_objects import SigningKey, VerificationKey

_PRIVATE_KEY_SUFFIX = ".private.pem"
_PUBLIC_KEY_SUFFIX = ".public.pem"


def _algorithm_name(key: object) -> str:
    if isinstance(key, (rsa.RSAPrivateKey, rsa.RSAPublicKey)):
        return "rsa"
    if isinstance(key, (ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey)):
        return "ecdsa"
    raise ValueError(f"Unsupported key type: {type(key).__name__}")


class LocalFileKeyRepository(KeyRepository):
    """Reads PEM-encoded key pairs from a directory.

    Expected layout (one pair per ``key_id``)::

        <keys_directory>/<key_id>.private.pem
        <keys_directory>/<key_id>.public.pem

    ``trusted_key_ids`` returns every ``key_id`` with a ``.public.pem`` file
    present, unless restricted via ``trusted_key_ids_override``.
    """

    def __init__(
        self,
        keys_directory: Path,
        trusted_key_ids_override: frozenset[str] | None = None,
    ) -> None:
        self._keys_directory = keys_directory
        self._trusted_key_ids_override = trusted_key_ids_override

    def get_signing_key(self, key_id: str) -> SigningKey:
        """See ``KeyRepository.get_signing_key``."""
        path = self._keys_directory / f"{key_id}{_PRIVATE_KEY_SUFFIX}"
        try:
            pem = path.read_bytes()
        except OSError as exc:
            raise SigningError(f"Cannot read private key for {key_id!r} at {path}: {exc}") from exc

        try:
            private_key = serialization.load_pem_private_key(pem, password=None)
            algorithm = _algorithm_name(private_key)
        except (ValueError, TypeError) as exc:
            raise SigningError(f"Invalid private key material for {key_id!r}: {exc}") from exc

        return SigningKey(key_id=key_id, algorithm=algorithm, private_key_material=pem)

    def get_verification_key(self, key_id: str) -> VerificationKey:
        """See ``KeyRepository.get_verification_key``."""
        path = self._keys_directory / f"{key_id}{_PUBLIC_KEY_SUFFIX}"
        try:
            pem = path.read_bytes()
        except OSError as exc:
            raise VerificationError(
                f"Cannot read public key for {key_id!r} at {path}: {exc}"
            ) from exc

        try:
            public_key = serialization.load_pem_public_key(pem)
            algorithm = _algorithm_name(public_key)
        except (ValueError, TypeError) as exc:
            raise VerificationError(f"Invalid public key material for {key_id!r}: {exc}") from exc

        return VerificationKey(key_id=key_id, algorithm=algorithm, public_key_material=pem)

    def trusted_key_ids(self) -> frozenset[str]:
        """See ``KeyRepository.trusted_key_ids``."""
        available = frozenset(
            path.name.removesuffix(_PUBLIC_KEY_SUFFIX)
            for path in self._keys_directory.glob(f"*{_PUBLIC_KEY_SUFFIX}")
        )
        if self._trusted_key_ids_override is None:
            return available
        return available & self._trusted_key_ids_override
