"""Unit tests for ``domain.models.dsse`` -- pure data, no doubles needed."""

from __future__ import annotations

import base64
import json

from hpc_provenance.domain.models.dsse import DSSEEnvelope, DSSESignature


def test_signature_to_dict_matches_dsse_shape() -> None:
    signature = DSSESignature(key_id="key-1", signature=b"sig-bytes")

    assert signature.to_dict() == {
        "keyid": "key-1",
        "sig": base64.b64encode(b"sig-bytes").decode("ascii"),
    }


def test_signature_to_dict_uses_empty_string_for_missing_key_id() -> None:
    signature = DSSESignature(key_id=None, signature=b"sig-bytes")

    assert signature.to_dict()["keyid"] == ""


def test_signature_from_dict_round_trips_to_dict() -> None:
    signature = DSSESignature(key_id="key-1", signature=b"sig-bytes")

    assert DSSESignature.from_dict(signature.to_dict()) == signature


def test_signature_from_dict_empty_keyid_becomes_none() -> None:
    data = {"keyid": "", "sig": base64.b64encode(b"sig-bytes").decode("ascii")}

    assert DSSESignature.from_dict(data) == DSSESignature(key_id=None, signature=b"sig-bytes")


def test_envelope_to_dict_matches_dsse_shape() -> None:
    envelope = DSSEEnvelope(
        payload=b'{"hello": "world"}',
        payload_type="application/vnd.in-toto+json",
        signatures=(DSSESignature(key_id="key-1", signature=b"sig-bytes"),),
    )

    assert envelope.to_dict() == {
        "payload": base64.b64encode(b'{"hello": "world"}').decode("ascii"),
        "payloadType": "application/vnd.in-toto+json",
        "signatures": [
            {"keyid": "key-1", "sig": base64.b64encode(b"sig-bytes").decode("ascii")},
        ],
    }


def test_envelope_to_dict_handles_no_signatures() -> None:
    envelope = DSSEEnvelope(payload=b"payload", payload_type="text/plain", signatures=())

    assert envelope.to_dict()["signatures"] == []


def test_envelope_to_json_round_trips_to_dict() -> None:
    envelope = DSSEEnvelope(
        payload=b'{"hello": "world"}',
        payload_type="application/vnd.in-toto+json",
        signatures=(DSSESignature(key_id="key-1", signature=b"sig-bytes"),),
    )

    assert json.loads(envelope.to_json()) == envelope.to_dict()


def test_envelope_from_dict_round_trips_to_dict() -> None:
    envelope = DSSEEnvelope(
        payload=b'{"hello": "world"}',
        payload_type="application/vnd.in-toto+json",
        signatures=(
            DSSESignature(key_id="key-1", signature=b"sig-1"),
            DSSESignature(key_id="key-2", signature=b"sig-2"),
        ),
    )

    assert DSSEEnvelope.from_dict(envelope.to_dict()) == envelope


def test_envelope_from_json_round_trips_to_json() -> None:
    envelope = DSSEEnvelope(
        payload=b'{"hello": "world"}',
        payload_type="application/vnd.in-toto+json",
        signatures=(DSSESignature(key_id="key-1", signature=b"sig-bytes"),),
    )

    assert DSSEEnvelope.from_json(envelope.to_json()) == envelope


def test_envelope_from_dict_handles_missing_signatures() -> None:
    data = {
        "payload": base64.b64encode(b"payload").decode("ascii"),
        "payloadType": "text/plain",
    }

    envelope = DSSEEnvelope.from_dict(data)

    assert envelope.signatures == ()
