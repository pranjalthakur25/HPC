"""DSSE (Dead Simple Signing Envelope) domain models.

https://github.com/secure-systems-lab/dsse
"""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DSSESignature:
    """A single signature over a DSSE envelope's PAE-encoded payload."""

    key_id: str | None
    signature: bytes

    def to_dict(self) -> dict[str, str]:
        """Map this signature to its DSSE JSON shape: ``{"keyid", "sig"}``.

        ``sig`` is base64-encoded, per
        https://github.com/secure-systems-lab/dsse/blob/master/envelope.md.
        """
        return {
            "keyid": self.key_id or "",
            "sig": base64.b64encode(self.signature).decode("ascii"),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> DSSESignature:
        """Build a ``DSSESignature`` from its DSSE JSON shape."""
        key_id = data.get("keyid")
        return cls(
            key_id=str(key_id) if key_id else None,
            signature=base64.b64decode(str(data["sig"])),
        )


@dataclass(frozen=True, slots=True)
class DSSEEnvelope:
    """A signed payload (typically an in-toto Statement) plus signatures."""

    payload: bytes
    payload_type: str
    signatures: tuple[DSSESignature, ...]

    def to_dict(self) -> dict[str, object]:
        """Map this envelope to its DSSE JSON shape:
        ``{"payload", "payloadType", "signatures"}``.

        ``payload`` is base64-encoded, per
        https://github.com/secure-systems-lab/dsse/blob/master/envelope.md.
        """
        return {
            "payload": base64.b64encode(self.payload).decode("ascii"),
            "payloadType": self.payload_type,
            "signatures": [signature.to_dict() for signature in self.signatures],
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialize ``to_dict()`` as a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> DSSEEnvelope:
        """Build a ``DSSEEnvelope`` from its DSSE JSON shape."""
        signatures = data.get("signatures", [])
        if not isinstance(signatures, list):
            signatures = []
        return cls(
            payload=base64.b64decode(str(data["payload"])),
            payload_type=str(data["payloadType"]),
            signatures=tuple(DSSESignature.from_dict(signature) for signature in signatures),
        )

    @classmethod
    def from_json(cls, text: str) -> DSSEEnvelope:
        """Build a ``DSSEEnvelope`` from its DSSE JSON string representation."""
        return cls.from_dict(json.loads(text))
