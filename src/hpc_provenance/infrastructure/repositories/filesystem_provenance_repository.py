"""Filesystem-backed implementation of ``ProvenanceRepository``."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from hpc_provenance.domain.exceptions import ProvenanceRecordNotFoundError
from hpc_provenance.domain.interfaces.repositories import (
    ProvenanceQuery,
    ProvenanceRecordId,
    ProvenanceRecordSummary,
    ProvenanceRepository,
)
from hpc_provenance.domain.models.dsse import DSSEEnvelope

_ENVELOPE_SUFFIX = ".dsse.json"
_META_SUFFIX = ".meta.json"


class FilesystemProvenanceRepository(ProvenanceRepository):
    """Stores each ``DSSEEnvelope`` as a JSON file under ``root_directory``,
    alongside a small sidecar metadata file used by ``list``.
    """

    def __init__(self, root_directory: Path) -> None:
        self._root_directory = root_directory

    def save(
        self, envelope: DSSEEnvelope, *, metadata: Mapping[str, str] | None = None
    ) -> ProvenanceRecordId:
        """See ``ProvenanceRepository.save``."""
        self._root_directory.mkdir(parents=True, exist_ok=True)

        record_id = ProvenanceRecordId(value=str(uuid4()))
        (self._root_directory / f"{record_id.value}{_ENVELOPE_SUFFIX}").write_text(
            envelope.to_json()
        )

        meta = {
            "payloadType": envelope.payload_type,
            "createdAt": datetime.now(UTC).isoformat(),
            "metadata": dict(metadata or {}),
        }
        (self._root_directory / f"{record_id.value}{_META_SUFFIX}").write_text(
            json.dumps(meta, indent=2)
        )

        return record_id

    def get(self, record_id: ProvenanceRecordId) -> DSSEEnvelope:
        """See ``ProvenanceRepository.get``.

        Raises:
            ProvenanceRecordNotFoundError: if the backing file is missing.
        """
        path = self._root_directory / f"{record_id.value}{_ENVELOPE_SUFFIX}"
        try:
            text = path.read_text()
        except OSError as exc:
            raise ProvenanceRecordNotFoundError(record_id.value) from exc
        return DSSEEnvelope.from_json(text)

    def list(self, query: ProvenanceQuery | None = None) -> Sequence[ProvenanceRecordSummary]:
        """See ``ProvenanceRepository.list``."""
        summaries: list[ProvenanceRecordSummary] = []
        for meta_path in sorted(self._root_directory.glob(f"*{_META_SUFFIX}")):
            data = json.loads(meta_path.read_text())
            created_at = datetime.fromisoformat(data["createdAt"])
            metadata: Mapping[str, str] = data.get("metadata", {})

            if query is not None and not _matches(query, created_at, metadata):
                continue

            summaries.append(
                ProvenanceRecordSummary(
                    record_id=ProvenanceRecordId(value=meta_path.name.removesuffix(_META_SUFFIX)),
                    payload_type=data["payloadType"],
                    created_at=created_at,
                    metadata=metadata,
                )
            )
        return tuple(summaries)


def _matches(query: ProvenanceQuery, created_at: datetime, metadata: Mapping[str, str]) -> bool:
    if query.created_after is not None and created_at < query.created_after:
        return False
    if query.created_before is not None and created_at > query.created_before:
        return False
    if query.job_id is not None and metadata.get("job_id") != query.job_id:
        return False
    if query.subject_digest is not None and metadata.get("subject_digest") != query.subject_digest:
        return False
    return True
