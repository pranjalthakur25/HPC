"""Unit tests for ``SignProvenanceUseCase``."""

from __future__ import annotations

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from hpc_provenance.application.dto.requests import SignProvenanceRequest
from hpc_provenance.application.use_cases.sign_provenance import SignProvenanceUseCase
from hpc_provenance.domain.models.in_toto import InTotoStatement
from hpc_provenance.domain.models.provenance import ResourceDescriptor
from hpc_provenance.domain.value_objects import SigningKey, VerificationKey
from hpc_provenance.infrastructure.signing.dsse_envelope_builder import DsseEnvelopeBuilder
from hpc_provenance.infrastructure.signing.dsse_signer import DsseSigner
from hpc_provenance.infrastructure.signing.payload_signers import (
    RSAPayloadSigner,
    create_payload_signer,
)
from tests.fakes.repositories import InMemoryKeyRepository, InMemoryProvenanceRepository


def _statement() -> InTotoStatement:
    return InTotoStatement(
        subjects=(ResourceDescriptor(name="model.safetensors", digest={"sha256": "b" * 64}),),
        predicate_type="https://slsa.dev/provenance/v1",
        predicate={"buildDefinition": {}, "runDetails": {}},
    )


def test_execute_signs_statement_and_persists_envelope(
    rsa_key_pair: tuple[SigningKey, VerificationKey],
) -> None:
    signing_key, _ = rsa_key_pair
    key_repository = InMemoryKeyRepository(signing_keys={signing_key.key_id: signing_key})
    provenance_repository = InMemoryProvenanceRepository()

    use_case = SignProvenanceUseCase(
        envelope_signer=DsseSigner(),
        key_repository=key_repository,
        provenance_repository=provenance_repository,
        payload_signer_factory=create_payload_signer,
    )

    statement = _statement()
    request = SignProvenanceRequest(
        statement=statement, signing_key_ids=(signing_key.key_id,), metadata={"job_id": "123456"}
    )

    result = use_case.execute(request)

    assert len(result.envelope.signatures) == 1
    assert result.envelope.signatures[0].key_id == signing_key.key_id
    assert provenance_repository.get(result.record_id) == result.envelope
    assert provenance_repository.list()[0].metadata == {"job_id": "123456"}


def test_execute_signature_is_verifiable_with_public_key(
    rsa_key_pair: tuple[SigningKey, VerificationKey],
) -> None:
    signing_key, verification_key = rsa_key_pair
    key_repository = InMemoryKeyRepository(signing_keys={signing_key.key_id: signing_key})
    provenance_repository = InMemoryProvenanceRepository()

    use_case = SignProvenanceUseCase(
        envelope_signer=DsseSigner(),
        key_repository=key_repository,
        provenance_repository=provenance_repository,
        payload_signer_factory=create_payload_signer,
    )

    statement = _statement()
    request = SignProvenanceRequest(statement=statement, signing_key_ids=(signing_key.key_id,))

    result = use_case.execute(request)

    envelope = result.envelope
    pae = DsseEnvelopeBuilder.pae(envelope.payload_type, envelope.payload)
    public_key = serialization.load_pem_public_key(verification_key.public_key_material)
    assert isinstance(public_key, rsa.RSAPublicKey)

    public_key.verify(
        envelope.signatures[0].signature,
        pae,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )


def test_execute_with_multiple_signing_keys_produces_one_signature_each(
    rsa_key_pair: tuple[SigningKey, VerificationKey],
    ec_key_pair: tuple[SigningKey, VerificationKey],
) -> None:
    rsa_signing_key, _ = rsa_key_pair
    ec_signing_key, _ = ec_key_pair
    key_repository = InMemoryKeyRepository(
        signing_keys={
            rsa_signing_key.key_id: rsa_signing_key,
            ec_signing_key.key_id: ec_signing_key,
        }
    )

    use_case = SignProvenanceUseCase(
        envelope_signer=DsseSigner(),
        key_repository=key_repository,
        provenance_repository=InMemoryProvenanceRepository(),
        payload_signer_factory=create_payload_signer,
    )

    request = SignProvenanceRequest(
        statement=_statement(),
        signing_key_ids=(rsa_signing_key.key_id, ec_signing_key.key_id),
    )

    result = use_case.execute(request)

    assert {signature.key_id for signature in result.envelope.signatures} == {
        rsa_signing_key.key_id,
        ec_signing_key.key_id,
    }


def test_execute_uses_injected_payload_signer_factory(
    rsa_key_pair: tuple[SigningKey, VerificationKey],
) -> None:
    signing_key, _ = rsa_key_pair
    key_repository = InMemoryKeyRepository(signing_keys={signing_key.key_id: signing_key})
    calls: list[SigningKey] = []

    def factory(key: SigningKey) -> RSAPayloadSigner:
        calls.append(key)
        return RSAPayloadSigner(key)

    use_case = SignProvenanceUseCase(
        envelope_signer=DsseSigner(),
        key_repository=key_repository,
        provenance_repository=InMemoryProvenanceRepository(),
        payload_signer_factory=factory,
    )

    request = SignProvenanceRequest(statement=_statement(), signing_key_ids=(signing_key.key_id,))
    use_case.execute(request)

    assert calls == [signing_key]
