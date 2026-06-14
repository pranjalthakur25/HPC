"""Builds DSSE envelopes from in-toto Statements.

Implements the DSSE v1 Pre-Authentication Encoding (PAE) and assembles
``DSSEEnvelope`` instances from a canonical JSON payload plus signatures.

https://github.com/secure-systems-lab/dsse/blob/master/protocol.md
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from hpc_provenance.domain.models.dsse import DSSEEnvelope, DSSESignature
from hpc_provenance.domain.models.in_toto import InTotoStatement

DSSE_PAYLOAD_TYPE = "application/vnd.in-toto+json"
"""The in-toto payload type used for DSSE envelopes carrying a Statement."""


class DsseEnvelopeBuilder:
    """Encodes in-toto Statements as DSSE payloads and assembles envelopes."""

    def __init__(self, payload_type: str = DSSE_PAYLOAD_TYPE) -> None:
        self.payload_type = payload_type

    def encode_payload(self, statement: InTotoStatement) -> bytes:
        """Serialize ``statement`` to the canonical JSON bytes used as the
        DSSE payload.
        """
        return json.dumps(statement.to_dict(), separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )

    @staticmethod
    def pae(payload_type: str, payload: bytes) -> bytes:
        """Compute the DSSE v1 Pre-Authentication Encoding for ``payload``.

        ``PAE(type, body) = "DSSEv1" + SP + LEN(type) + SP + type + SP +
        LEN(body) + SP + body``
        """
        encoded_type = payload_type.encode("utf-8")
        return b"DSSEv1 %d %b %d %b" % (len(encoded_type), encoded_type, len(payload), payload)

    def build(
        self, statement: InTotoStatement, signatures: Sequence[DSSESignature] = ()
    ) -> DSSEEnvelope:
        """Encode ``statement`` and assemble a ``DSSEEnvelope`` carrying
        ``signatures`` over its PAE.
        """
        payload = self.encode_payload(statement)
        return DSSEEnvelope(
            payload=payload, payload_type=self.payload_type, signatures=tuple(signatures)
        )
