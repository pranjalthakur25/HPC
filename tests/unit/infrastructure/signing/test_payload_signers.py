"""Unit tests for RSA/ECDSA ``PayloadSigner`` adapters."""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa

from hpc_provenance.domain.exceptions import SigningError
from hpc_provenance.domain.value_objects import SigningKey, VerificationKey
from hpc_provenance.infrastructure.signing.payload_signers import (
    ECDSAPayloadSigner,
    RSAPayloadSigner,
    create_payload_signer,
)


def test_rsa_signer_key_id_matches_signing_key(
    rsa_key_pair: tuple[SigningKey, VerificationKey],
) -> None:
    signing_key, _ = rsa_key_pair

    signer = RSAPayloadSigner(signing_key)

    assert signer.key_id == signing_key.key_id


def test_rsa_signer_produces_verifiable_pss_signature(
    rsa_key_pair: tuple[SigningKey, VerificationKey],
) -> None:
    signing_key, verification_key = rsa_key_pair
    signer = RSAPayloadSigner(signing_key)
    public_key = serialization.load_pem_public_key(verification_key.public_key_material)
    assert isinstance(public_key, rsa.RSAPublicKey)

    signature = signer.sign(b"hello world")

    public_key.verify(
        signature,
        b"hello world",
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )


def test_ecdsa_signer_produces_verifiable_signature(
    ec_key_pair: tuple[SigningKey, VerificationKey],
) -> None:
    signing_key, verification_key = ec_key_pair
    signer = ECDSAPayloadSigner(signing_key)
    public_key = serialization.load_pem_public_key(verification_key.public_key_material)
    assert isinstance(public_key, ec.EllipticCurvePublicKey)

    signature = signer.sign(b"hello world")

    public_key.verify(signature, b"hello world", ec.ECDSA(hashes.SHA256()))


def test_rsa_signer_rejects_ec_key(ec_key_pair: tuple[SigningKey, VerificationKey]) -> None:
    signing_key, _ = ec_key_pair

    with pytest.raises(SigningError):
        RSAPayloadSigner(signing_key)


def test_ecdsa_signer_rejects_rsa_key(rsa_key_pair: tuple[SigningKey, VerificationKey]) -> None:
    signing_key, _ = rsa_key_pair

    with pytest.raises(SigningError):
        ECDSAPayloadSigner(signing_key)


def test_rsa_signer_rejects_invalid_pem() -> None:
    bad_key = SigningKey(key_id="bad", algorithm="rsa", private_key_material=b"not a pem")

    with pytest.raises(SigningError):
        RSAPayloadSigner(bad_key)


def test_create_payload_signer_dispatches_on_algorithm(
    rsa_key_pair: tuple[SigningKey, VerificationKey],
    ec_key_pair: tuple[SigningKey, VerificationKey],
) -> None:
    rsa_signing_key, _ = rsa_key_pair
    ec_signing_key, _ = ec_key_pair

    assert isinstance(create_payload_signer(rsa_signing_key), RSAPayloadSigner)
    assert isinstance(create_payload_signer(ec_signing_key), ECDSAPayloadSigner)


def test_create_payload_signer_is_case_insensitive(
    rsa_key_pair: tuple[SigningKey, VerificationKey],
) -> None:
    signing_key, _ = rsa_key_pair
    upper_case = SigningKey(
        key_id=signing_key.key_id,
        algorithm="RSA",
        private_key_material=signing_key.private_key_material,
    )

    assert isinstance(create_payload_signer(upper_case), RSAPayloadSigner)


def test_create_payload_signer_rejects_unknown_algorithm() -> None:
    signing_key = SigningKey(key_id="x", algorithm="ed25519", private_key_material=b"")

    with pytest.raises(SigningError):
        create_payload_signer(signing_key)
