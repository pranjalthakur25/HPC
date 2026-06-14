"""Unit tests for ``DsseSigner``."""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa

from hpc_provenance.domain.exceptions import SigningError
from hpc_provenance.domain.models.dsse import DSSESignature
from hpc_provenance.domain.models.in_toto import InTotoStatement
from hpc_provenance.domain.models.provenance import ResourceDescriptor
from hpc_provenance.domain.value_objects import SigningKey, VerificationKey
from hpc_provenance.infrastructure.signing.dsse_envelope_builder import (
    DSSE_PAYLOAD_TYPE,
    DsseEnvelopeBuilder,
)
from hpc_provenance.infrastructure.signing.dsse_signer import DsseSigner
from hpc_provenance.infrastructure.signing.payload_signers import (
    ECDSAPayloadSigner,
    RSAPayloadSigner,
)
from tests.fakes.signing import FakePayloadSigner


def _statement() -> InTotoStatement:
    return InTotoStatement(
        subjects=(ResourceDescriptor(name="model.safetensors", digest={"sha256": "b" * 64}),),
        predicate_type="https://slsa.dev/provenance/v1",
        predicate={"buildDefinition": {}, "runDetails": {}},
    )


def test_sign_produces_envelope_with_expected_payload() -> None:
    signer = DsseSigner()
    statement = _statement()
    fake_signer = FakePayloadSigner(key_id_value="key-1", signature=b"sig-bytes")

    envelope = signer.sign(statement, [fake_signer])

    builder = DsseEnvelopeBuilder()
    assert envelope.payload == builder.encode_payload(statement)
    assert envelope.payload_type == DSSE_PAYLOAD_TYPE
    assert envelope.signatures == (DSSESignature(key_id="key-1", signature=b"sig-bytes"),)


def test_sign_with_multiple_signers_produces_one_signature_each() -> None:
    signer = DsseSigner()
    statement = _statement()
    signers = [
        FakePayloadSigner(key_id_value="key-1", signature=b"sig-1"),
        FakePayloadSigner(key_id_value="key-2", signature=b"sig-2"),
    ]

    envelope = signer.sign(statement, signers)

    assert envelope.signatures == (
        DSSESignature(key_id="key-1", signature=b"sig-1"),
        DSSESignature(key_id="key-2", signature=b"sig-2"),
    )


def test_sign_requires_at_least_one_signer() -> None:
    signer = DsseSigner()

    with pytest.raises(SigningError):
        signer.sign(_statement(), [])


def test_sign_with_real_rsa_key_produces_verifiable_signature(
    rsa_key_pair: tuple[SigningKey, VerificationKey],
) -> None:
    signing_key, verification_key = rsa_key_pair
    signer = DsseSigner()
    statement = _statement()

    envelope = signer.sign(statement, [RSAPayloadSigner(signing_key)])

    assert len(envelope.signatures) == 1
    signature = envelope.signatures[0]
    assert signature.key_id == signing_key.key_id

    pae = DsseEnvelopeBuilder.pae(envelope.payload_type, envelope.payload)
    public_key = serialization.load_pem_public_key(verification_key.public_key_material)
    assert isinstance(public_key, rsa.RSAPublicKey)
    public_key.verify(
        signature.signature,
        pae,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )


def test_sign_with_real_ecdsa_key_produces_verifiable_signature(
    ec_key_pair: tuple[SigningKey, VerificationKey],
) -> None:
    signing_key, verification_key = ec_key_pair
    signer = DsseSigner()
    statement = _statement()

    envelope = signer.sign(statement, [ECDSAPayloadSigner(signing_key)])

    assert len(envelope.signatures) == 1
    signature = envelope.signatures[0]
    assert signature.key_id == signing_key.key_id

    pae = DsseEnvelopeBuilder.pae(envelope.payload_type, envelope.payload)
    public_key = serialization.load_pem_public_key(verification_key.public_key_material)
    assert isinstance(public_key, ec.EllipticCurvePublicKey)
    public_key.verify(signature.signature, pae, ec.ECDSA(hashes.SHA256()))
