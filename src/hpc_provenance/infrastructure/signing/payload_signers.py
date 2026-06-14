"""``cryptography``-backed ``PayloadSigner`` adapters for RSA and ECDSA keys."""

from __future__ import annotations

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.asymmetric.types import PrivateKeyTypes

from hpc_provenance.domain.exceptions import SigningError
from hpc_provenance.domain.interfaces.signing import PayloadSigner
from hpc_provenance.domain.value_objects import SigningKey

_RSA_PADDING = padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH)
_RSA_ALGORITHM = hashes.SHA256()
_EC_ALGORITHM = ec.ECDSA(hashes.SHA256())


def _load_private_key(signing_key: SigningKey) -> PrivateKeyTypes:
    try:
        return serialization.load_pem_private_key(
            signing_key.private_key_material, password=None
        )
    except (ValueError, TypeError) as exc:
        raise SigningError(
            f"Invalid private key material for {signing_key.key_id!r}: {exc}"
        ) from exc


class RSAPayloadSigner:
    """Signs payloads with an RSA private key using RSASSA-PSS + SHA-256."""

    def __init__(self, signing_key: SigningKey) -> None:
        self._key_id = signing_key.key_id
        private_key = _load_private_key(signing_key)
        if not isinstance(private_key, rsa.RSAPrivateKey):
            raise SigningError(
                f"Key {signing_key.key_id!r} (algorithm={signing_key.algorithm!r}) is not an "
                f"RSA private key"
            )
        self._private_key: rsa.RSAPrivateKey = private_key

    @property
    def key_id(self) -> str:
        return self._key_id

    def sign(self, payload: bytes) -> bytes:
        return self._private_key.sign(payload, _RSA_PADDING, _RSA_ALGORITHM)


class ECDSAPayloadSigner:
    """Signs payloads with an ECDSA private key using ECDSA + SHA-256."""

    def __init__(self, signing_key: SigningKey) -> None:
        self._key_id = signing_key.key_id
        private_key = _load_private_key(signing_key)
        if not isinstance(private_key, ec.EllipticCurvePrivateKey):
            raise SigningError(
                f"Key {signing_key.key_id!r} (algorithm={signing_key.algorithm!r}) is not an "
                f"EC private key"
            )
        self._private_key: ec.EllipticCurvePrivateKey = private_key

    @property
    def key_id(self) -> str:
        return self._key_id

    def sign(self, payload: bytes) -> bytes:
        return self._private_key.sign(payload, _EC_ALGORITHM)


def create_payload_signer(signing_key: SigningKey) -> PayloadSigner:
    """Return the ``PayloadSigner`` matching ``signing_key.algorithm``.

    Raises:
        SigningError: if ``signing_key.algorithm`` is not ``"rsa"`` or
            ``"ecdsa"`` (case-insensitive), or the key material does not
            match the algorithm.
    """
    match signing_key.algorithm.lower():
        case "rsa":
            return RSAPayloadSigner(signing_key)
        case "ecdsa":
            return ECDSAPayloadSigner(signing_key)
        case other:
            raise SigningError(f"Unsupported signing key algorithm: {other!r}")
