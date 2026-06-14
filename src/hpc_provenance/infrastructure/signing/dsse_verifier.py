"""DSSE envelope verifier: checks RSA / ECDSA signatures and policy."""

from __future__ import annotations

import json
from collections.abc import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa

from hpc_provenance.domain.enums import IssueSeverity
from hpc_provenance.domain.exceptions import VerificationError
from hpc_provenance.domain.interfaces.signing import DSSEEnvelopeVerifier
from hpc_provenance.domain.models.dsse import DSSEEnvelope
from hpc_provenance.domain.models.verification import (
    VerificationIssue,
    VerificationPolicy,
    VerificationResult,
)
from hpc_provenance.domain.value_objects import VerificationKey
from hpc_provenance.infrastructure.signing.dsse_envelope_builder import DsseEnvelopeBuilder

_RSA_PADDING = padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH)
_RSA_ALGORITHM = hashes.SHA256()
_EC_ALGORITHM = ec.ECDSA(hashes.SHA256())


class DsseVerifier(DSSEEnvelopeVerifier):
    """Verifies DSSE signatures (RSA / ECDSA) and checks the decoded in-toto
    Statement against a ``VerificationPolicy``.
    """

    def verify(
        self,
        envelope: DSSEEnvelope,
        policy: VerificationPolicy,
        verification_keys: Mapping[str, VerificationKey],
    ) -> VerificationResult:
        pae = DsseEnvelopeBuilder.pae(envelope.payload_type, envelope.payload)

        issues: list[VerificationIssue] = []
        verified_key_ids: list[str] = []

        for signature in envelope.signatures:
            key_id = signature.key_id
            if key_id is None or key_id not in verification_keys:
                issues.append(
                    VerificationIssue(
                        code="UNKNOWN_KEY",
                        message=f"No verification key available for key id {key_id!r}",
                        severity=IssueSeverity.WARNING,
                    )
                )
                continue

            verification_key = verification_keys[key_id]
            if not _verify_signature(verification_key, pae, signature.signature):
                issues.append(
                    VerificationIssue(
                        code="INVALID_SIGNATURE",
                        message=f"Signature from key id {key_id!r} did not verify",
                        severity=IssueSeverity.ERROR,
                    )
                )
                continue

            if key_id in policy.trusted_key_ids:
                verified_key_ids.append(key_id)

        issues.extend(_check_policy(envelope, policy))

        is_valid = bool(verified_key_ids) and not any(
            issue.severity == IssueSeverity.ERROR for issue in issues
        )
        return VerificationResult(
            is_valid=is_valid, issues=tuple(issues), verified_key_ids=tuple(verified_key_ids)
        )


def _verify_signature(verification_key: VerificationKey, pae: bytes, signature: bytes) -> bool:
    try:
        public_key = serialization.load_pem_public_key(verification_key.public_key_material)
    except (ValueError, TypeError) as exc:
        raise VerificationError(
            f"Invalid public key material for {verification_key.key_id!r}: {exc}"
        ) from exc

    try:
        if isinstance(public_key, rsa.RSAPublicKey):
            public_key.verify(signature, pae, _RSA_PADDING, _RSA_ALGORITHM)
        elif isinstance(public_key, ec.EllipticCurvePublicKey):
            public_key.verify(signature, pae, _EC_ALGORITHM)
        else:
            raise VerificationError(
                f"Unsupported public key type for {verification_key.key_id!r}: "
                f"{type(public_key).__name__}"
            )
    except InvalidSignature:
        return False
    return True


def _as_mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _check_policy(envelope: DSSEEnvelope, policy: VerificationPolicy) -> list[VerificationIssue]:
    try:
        decoded: object = json.loads(envelope.payload)
    except json.JSONDecodeError as exc:
        raise VerificationError(f"Envelope payload is not valid JSON: {exc}") from exc

    statement = _as_mapping(decoded)
    predicate = _as_mapping(statement.get("predicate"))

    issues: list[VerificationIssue] = []

    if policy.required_predicate_type is not None:
        actual_type = statement.get("predicateType")
        if actual_type != policy.required_predicate_type:
            issues.append(
                VerificationIssue(
                    code="PREDICATE_TYPE_MISMATCH",
                    message=(
                        f"Expected predicateType {policy.required_predicate_type!r}, "
                        f"got {actual_type!r}"
                    ),
                    severity=IssueSeverity.ERROR,
                )
            )

    if policy.expected_builder_id is not None:
        run_details = _as_mapping(predicate.get("runDetails"))
        builder = _as_mapping(run_details.get("builder"))
        actual_builder_id = builder.get("id")
        if actual_builder_id != policy.expected_builder_id:
            issues.append(
                VerificationIssue(
                    code="BUILDER_ID_MISMATCH",
                    message=(
                        f"Expected builder id {policy.expected_builder_id!r}, "
                        f"got {actual_builder_id!r}"
                    ),
                    severity=IssueSeverity.ERROR,
                )
            )

    if policy.expected_source_repo_uri is not None:
        build_definition = _as_mapping(predicate.get("buildDefinition"))
        resolved_dependencies = _as_list(build_definition.get("resolvedDependencies"))
        uris = {
            dependency.get("uri")
            for dependency in resolved_dependencies
            if isinstance(dependency, Mapping)
        }
        if policy.expected_source_repo_uri not in uris:
            issues.append(
                VerificationIssue(
                    code="SOURCE_REPO_MISMATCH",
                    message=(
                        f"Expected source repository "
                        f"{policy.expected_source_repo_uri!r} not found in "
                        f"resolvedDependencies"
                    ),
                    severity=IssueSeverity.ERROR,
                )
            )

    return issues
