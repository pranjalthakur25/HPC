"""Unit tests for ``DsseVerifier``."""

from __future__ import annotations

from hpc_provenance.domain.enums import IssueSeverity
from hpc_provenance.domain.models.dsse import DSSEEnvelope
from hpc_provenance.domain.models.in_toto import InTotoStatement
from hpc_provenance.domain.models.provenance import ResourceDescriptor
from hpc_provenance.domain.models.verification import VerificationPolicy
from hpc_provenance.domain.value_objects import SigningKey, VerificationKey
from hpc_provenance.infrastructure.signing.dsse_signer import DsseSigner
from hpc_provenance.infrastructure.signing.dsse_verifier import DsseVerifier
from hpc_provenance.infrastructure.signing.payload_signers import (
    ECDSAPayloadSigner,
    RSAPayloadSigner,
)


def _statement(**overrides: object) -> InTotoStatement:
    defaults: dict[str, object] = {
        "subjects": (ResourceDescriptor(name="model.safetensors", digest={"sha256": "b" * 64}),),
        "predicate_type": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "https://example.org/build-types/slurm-job/v1",
                "externalParameters": {},
                "internalParameters": {},
                "resolvedDependencies": [{"uri": "https://github.com/example/project.git"}],
            },
            "runDetails": {
                "builder": {"id": "https://example.org/hpc-provenance/builder/v1"},
                "metadata": {},
            },
        },
    }
    defaults.update(overrides)
    return InTotoStatement(**defaults)  # type: ignore[arg-type]


def _policy(**overrides: object) -> VerificationPolicy:
    defaults: dict[str, object] = {"trusted_key_ids": frozenset()}
    defaults.update(overrides)
    return VerificationPolicy(**defaults)  # type: ignore[arg-type]


def test_verify_succeeds_for_real_rsa_signature(
    rsa_key_pair: tuple[SigningKey, VerificationKey],
) -> None:
    signing_key, verification_key = rsa_key_pair
    envelope = DsseSigner().sign(_statement(), [RSAPayloadSigner(signing_key)])

    result = DsseVerifier().verify(
        envelope,
        _policy(trusted_key_ids=frozenset({signing_key.key_id})),
        {verification_key.key_id: verification_key},
    )

    assert result.is_valid is True
    assert result.verified_key_ids == (signing_key.key_id,)
    assert result.issues == ()


def test_verify_succeeds_for_real_ecdsa_signature(
    ec_key_pair: tuple[SigningKey, VerificationKey],
) -> None:
    signing_key, verification_key = ec_key_pair
    envelope = DsseSigner().sign(_statement(), [ECDSAPayloadSigner(signing_key)])

    result = DsseVerifier().verify(
        envelope,
        _policy(trusted_key_ids=frozenset({signing_key.key_id})),
        {verification_key.key_id: verification_key},
    )

    assert result.is_valid is True
    assert result.verified_key_ids == (signing_key.key_id,)


def test_verify_detects_tampered_payload(
    rsa_key_pair: tuple[SigningKey, VerificationKey],
) -> None:
    signing_key, verification_key = rsa_key_pair
    envelope = DsseSigner().sign(_statement(), [RSAPayloadSigner(signing_key)])
    tampered = DSSEEnvelope(
        payload=envelope.payload + b" ",
        payload_type=envelope.payload_type,
        signatures=envelope.signatures,
    )

    result = DsseVerifier().verify(
        tampered,
        _policy(trusted_key_ids=frozenset({signing_key.key_id})),
        {verification_key.key_id: verification_key},
    )

    assert result.is_valid is False
    assert result.verified_key_ids == ()
    assert any(issue.code == "INVALID_SIGNATURE" for issue in result.issues)
    assert all(issue.severity == IssueSeverity.ERROR for issue in result.issues)


def test_verify_reports_unknown_key(rsa_key_pair: tuple[SigningKey, VerificationKey]) -> None:
    signing_key, _ = rsa_key_pair
    envelope = DsseSigner().sign(_statement(), [RSAPayloadSigner(signing_key)])

    result = DsseVerifier().verify(envelope, _policy(), {})

    assert result.is_valid is False
    assert result.verified_key_ids == ()
    assert any(
        issue.code == "UNKNOWN_KEY" and issue.severity == IssueSeverity.WARNING
        for issue in result.issues
    )


def test_verify_excludes_untrusted_keys_from_verified_key_ids(
    rsa_key_pair: tuple[SigningKey, VerificationKey],
) -> None:
    signing_key, verification_key = rsa_key_pair
    envelope = DsseSigner().sign(_statement(), [RSAPayloadSigner(signing_key)])

    result = DsseVerifier().verify(
        envelope,
        _policy(trusted_key_ids=frozenset({"some-other-key"})),
        {verification_key.key_id: verification_key},
    )

    assert result.is_valid is False
    assert result.verified_key_ids == ()
    assert result.issues == ()  # signature is valid; just not trusted


def test_verify_checks_required_predicate_type(
    rsa_key_pair: tuple[SigningKey, VerificationKey],
) -> None:
    signing_key, verification_key = rsa_key_pair
    envelope = DsseSigner().sign(_statement(), [RSAPayloadSigner(signing_key)])

    result = DsseVerifier().verify(
        envelope,
        _policy(
            trusted_key_ids=frozenset({signing_key.key_id}),
            required_predicate_type="https://slsa.dev/provenance/v0.2",
        ),
        {verification_key.key_id: verification_key},
    )

    assert result.is_valid is False
    assert any(issue.code == "PREDICATE_TYPE_MISMATCH" for issue in result.issues)


def test_verify_checks_expected_builder_id(
    rsa_key_pair: tuple[SigningKey, VerificationKey],
) -> None:
    signing_key, verification_key = rsa_key_pair
    envelope = DsseSigner().sign(_statement(), [RSAPayloadSigner(signing_key)])

    result = DsseVerifier().verify(
        envelope,
        _policy(
            trusted_key_ids=frozenset({signing_key.key_id}),
            expected_builder_id="https://example.org/some-other-builder",
        ),
        {verification_key.key_id: verification_key},
    )

    assert result.is_valid is False
    assert any(issue.code == "BUILDER_ID_MISMATCH" for issue in result.issues)


def test_verify_checks_expected_source_repo_uri(
    rsa_key_pair: tuple[SigningKey, VerificationKey],
) -> None:
    signing_key, verification_key = rsa_key_pair
    envelope = DsseSigner().sign(_statement(), [RSAPayloadSigner(signing_key)])

    result = DsseVerifier().verify(
        envelope,
        _policy(
            trusted_key_ids=frozenset({signing_key.key_id}),
            expected_source_repo_uri="https://github.com/other/project.git",
        ),
        {verification_key.key_id: verification_key},
    )

    assert result.is_valid is False
    assert any(issue.code == "SOURCE_REPO_MISMATCH" for issue in result.issues)


def test_verify_multi_signature_envelope_with_one_untrusted_key(
    rsa_key_pair: tuple[SigningKey, VerificationKey],
    ec_key_pair: tuple[SigningKey, VerificationKey],
) -> None:
    rsa_signing_key, rsa_verification_key = rsa_key_pair
    ec_signing_key, ec_verification_key = ec_key_pair
    envelope = DsseSigner().sign(
        _statement(),
        [RSAPayloadSigner(rsa_signing_key), ECDSAPayloadSigner(ec_signing_key)],
    )

    result = DsseVerifier().verify(
        envelope,
        _policy(trusted_key_ids=frozenset({rsa_signing_key.key_id})),
        {
            rsa_verification_key.key_id: rsa_verification_key,
            ec_verification_key.key_id: ec_verification_key,
        },
    )

    assert result.is_valid is True
    assert result.verified_key_ids == (rsa_signing_key.key_id,)
    assert result.issues == ()
