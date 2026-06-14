"""Unit tests for ``DsseEnvelopeBuilder`` -- PAE encoding and envelope assembly."""

from __future__ import annotations

import json

from hpc_provenance.domain.models.dsse import DSSESignature
from hpc_provenance.domain.models.in_toto import InTotoStatement
from hpc_provenance.domain.models.provenance import ResourceDescriptor
from hpc_provenance.infrastructure.signing.dsse_envelope_builder import (
    DSSE_PAYLOAD_TYPE,
    DsseEnvelopeBuilder,
)


def _statement() -> InTotoStatement:
    return InTotoStatement(
        subjects=(ResourceDescriptor(name="model.safetensors", digest={"sha256": "b" * 64}),),
        predicate_type="https://slsa.dev/provenance/v1",
        predicate={"buildDefinition": {}, "runDetails": {}},
    )


def test_default_payload_type_is_in_toto_json() -> None:
    builder = DsseEnvelopeBuilder()

    assert builder.payload_type == DSSE_PAYLOAD_TYPE == "application/vnd.in-toto+json"


def test_encode_payload_matches_statement_to_dict() -> None:
    builder = DsseEnvelopeBuilder()
    statement = _statement()

    assert json.loads(builder.encode_payload(statement)) == statement.to_dict()


def test_encode_payload_is_deterministic() -> None:
    builder = DsseEnvelopeBuilder()
    statement = _statement()

    assert builder.encode_payload(statement) == builder.encode_payload(statement)


def test_pae_matches_dsse_spec_worked_example() -> None:
    # https://github.com/secure-systems-lab/dsse/blob/master/protocol.md
    pae = DsseEnvelopeBuilder.pae("http://example.com/HelloWorld", b"hello world")

    assert pae == b"DSSEv1 29 http://example.com/HelloWorld 11 hello world"


def test_build_assembles_envelope_with_payload_and_signatures() -> None:
    builder = DsseEnvelopeBuilder()
    statement = _statement()
    signatures = (DSSESignature(key_id="key-1", signature=b"sig"),)

    envelope = builder.build(statement, signatures)

    assert envelope.payload == builder.encode_payload(statement)
    assert envelope.payload_type == DSSE_PAYLOAD_TYPE
    assert envelope.signatures == signatures


def test_build_defaults_to_no_signatures() -> None:
    builder = DsseEnvelopeBuilder()
    statement = _statement()

    envelope = builder.build(statement)

    assert envelope.signatures == ()


def test_custom_payload_type_is_used() -> None:
    builder = DsseEnvelopeBuilder(payload_type="application/vnd.custom+json")
    statement = _statement()

    envelope = builder.build(statement)

    assert envelope.payload_type == "application/vnd.custom+json"
