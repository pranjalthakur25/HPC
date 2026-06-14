"""Unit tests for ``FilesystemProvenanceRepository``."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from hpc_provenance.domain.exceptions import ProvenanceRecordNotFoundError
from hpc_provenance.domain.interfaces.repositories import ProvenanceQuery, ProvenanceRecordId
from hpc_provenance.domain.models.dsse import DSSEEnvelope, DSSESignature
from hpc_provenance.infrastructure.repositories.filesystem_provenance_repository import (
    FilesystemProvenanceRepository,
)


def _envelope() -> DSSEEnvelope:
    return DSSEEnvelope(
        payload=b'{"hello": "world"}',
        payload_type="application/vnd.in-toto+json",
        signatures=(DSSESignature(key_id="key-1", signature=b"sig-bytes"),),
    )


def test_save_creates_root_directory(tmp_path: Path) -> None:
    root = tmp_path / "provenance"
    repository = FilesystemProvenanceRepository(root_directory=root)

    repository.save(_envelope())

    assert root.is_dir()


def test_save_returns_record_id_and_get_round_trips(tmp_path: Path) -> None:
    repository = FilesystemProvenanceRepository(root_directory=tmp_path)
    envelope = _envelope()

    record_id = repository.save(envelope)

    assert repository.get(record_id) == envelope


def test_get_raises_for_unknown_record(tmp_path: Path) -> None:
    repository = FilesystemProvenanceRepository(root_directory=tmp_path)

    with pytest.raises(ProvenanceRecordNotFoundError):
        repository.get(ProvenanceRecordId(value="unknown-id"))


def test_list_returns_summary_with_metadata(tmp_path: Path) -> None:
    repository = FilesystemProvenanceRepository(root_directory=tmp_path)
    record_id = repository.save(_envelope(), metadata={"job_id": "123456"})

    summaries = repository.list()

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.record_id == record_id
    assert summary.payload_type == "application/vnd.in-toto+json"
    assert summary.metadata == {"job_id": "123456"}


def test_list_filters_by_job_id(tmp_path: Path) -> None:
    repository = FilesystemProvenanceRepository(root_directory=tmp_path)
    matching_id = repository.save(_envelope(), metadata={"job_id": "123456"})
    repository.save(_envelope(), metadata={"job_id": "other"})

    summaries = repository.list(ProvenanceQuery(job_id="123456"))

    assert [summary.record_id for summary in summaries] == [matching_id]


def test_list_filters_by_created_after_and_before(tmp_path: Path) -> None:
    repository = FilesystemProvenanceRepository(root_directory=tmp_path)
    record_id = repository.save(_envelope())

    now = datetime.now(UTC)
    assert repository.list(ProvenanceQuery(created_after=now + timedelta(days=1))) == ()
    assert [
        summary.record_id
        for summary in repository.list(ProvenanceQuery(created_before=now + timedelta(days=1)))
    ] == [record_id]


def test_list_returns_empty_for_missing_directory(tmp_path: Path) -> None:
    repository = FilesystemProvenanceRepository(root_directory=tmp_path / "does-not-exist")

    assert repository.list() == ()
